"""
A Shotgrid Events listener leecher for Ayon.

This service will continually run and query the EventLogEntry table from
Shotgrid and converts them to Ayon events, and can be configured from the Ayon
Addon settings page.
"""
import sys
import time
import signal
import socket
import traceback
from typing import Any
from pprint import pformat

from utils import get_logger

from constants import (
    SG_EVENT_TYPES,
    SG_EVENT_QUERY_FIELDS,
)

import ayon_api
import shotgun_api3

LAST_EVENT_QUERY = """query LastShotgridEvent($eventTopic: String!) {
  events(last: 1, topics: [$eventTopic]) {
    edges {
      node {
        hash
      }
    }
  }
}
"""


class ShotgridListener:
    log = get_logger(__file__)

    def __init__(self):
        """Ensure both Ayon and Shotgrid connections are available.

        Set up common needed attributes and handle shotgrid connection
        closure via signal handlers.

        """
        self.log.info("Initializing the Shotgrid Listener.")

        try:
            self.settings = ayon_api.get_service_addon_settings()
            service_settings = self.settings["service_settings"]

            self.sg_url = self.settings["shotgrid_server"]
            self.sg_project_code_field = self.settings[
                "shotgrid_project_code_field"]

            # get server op related ShotGrid script api properties
            shotgrid_secret = ayon_api.get_secret(
                service_settings["script_key"])

            if isinstance(shotgrid_secret, list):
                raise ValueError(
                    "Shotgrid API Key not found. Make sure to set it in the "
                    "Addon System settings. "
                    "`ayon+settings://shotgrid/service_settings/script_key`"
                )

            self.sg_api_key = shotgrid_secret.get("value")
            if not self.sg_api_key:
                raise ValueError(
                    "Shotgrid API Key not found. Make sure to set it in the "
                    "Addon System settings."
                )

            self.sg_script_name = service_settings["script_name"]
            if not self.sg_script_name:
                raise ValueError(
                    "Shotgrid Script Name not found. Make sure to set it in "
                    "the Addon System settings."
                )

            self.custom_attribs_map = {
                attr["ayon"]: attr["sg"]
                for attr in self.settings["compatibility_settings"]["custom_attribs_map"]  # noqa: E501
                if attr["sg"]
            }
            self.custom_sg_attribs = set(self.custom_attribs_map.values())

            # TODO: implement a way to handle status_list and tags
            self.custom_attribs_map.update({
                # "status": "status_list",
                "tags": "tags"
            })

            self.sg_enabled_entities = self.settings["compatibility_settings"]["shotgrid_enabled_entities"]  # noqa: E501

            try:
                self.shotgrid_polling_frequency = int(
                    service_settings["polling_frequency"]
                )
            except Exception:
                self.shotgrid_polling_frequency = 10

        except Exception as e:
            self.log.error(
                "Unable to get Addon settings from the server.")
            raise e

        try:
            self.sg_session = shotgun_api3.Shotgun(
                self.sg_url,
                script_name=self.sg_script_name,
                api_key=self.sg_api_key
            )
            self.sg_session.connect()
        except Exception as e:
            self.log.error("Unable to connect to Shotgrid Instance:")
            raise e

        signal.signal(signal.SIGINT, self._signal_teardown_handler)
        signal.signal(signal.SIGTERM, self._signal_teardown_handler)

    def _signal_teardown_handler(self, signalnum, frame):
        self.log.warning("Process stop requested. Terminating process.")
        self.sg_session.close()
        self.log.warning("Termination finished.")
        sys.exit(0)

    def _build_shotgrid_filters(self, sg_projects):
        """Build SG filters for Events query.

        We want to filter out all the Events in the SG database that do not
        meet our needs:
            1) Events of Projects with "AYON Auto Sync" enabled.
            2) Events on entities and type for entities we track.

        Args:
            sg_projects (list): List of Shotgrid Project IDs.

        Returns:
            filters (list): Filter to apply to the SG query.
        """
        filters = []

        if not sg_projects:
            return []

        filters.append(["project", "in", sg_projects])

        if sg_event_types := self._get_supported_event_types():
            filters.append(["event_type", "in", sg_event_types])

        return filters

    def _get_supported_event_types(self) -> list[str]:
        sg_event_types = []
        for entity_type in self.sg_enabled_entities:
            sg_event_types.extend(
                event_name.format(entity_type) for event_name in SG_EVENT_TYPES
            )
        return sg_event_types

    def _find_last_event_id(self):
        response = ayon_api.query_graphql(
            LAST_EVENT_QUERY,
            {"eventTopic": "shotgrid.event"},
        )
        if response.errors:
            self.log.error(str(response.errors))
            return None
        data = response.data["data"]
        for node in data["events"]["edges"]:
            return node["node"]["hash"]
        return None

    def _get_last_event_processed(self, sg_filters):
        """Find the Event ID for the last SG processed event.

        First attempt to find it via AYON, if none is found we get the last
        matching event from Shotgrid.

        Returns:
            last_event_id (int): The last known Event id.
        """
        last_event_id = self._find_last_event_id()
        if not last_event_id:
            last_event = self.sg_session.find_one(
                "EventLogEntry",
                filters=sg_filters,
                fields=["id", "project"],
                order=[{"column": "id", "direction": "desc"}],
            )
            last_event_id = last_event["id"]

        return last_event_id

    def start_listening(self):
        """Main loop querying the Shotgrid database for new events

        Since Shotgrid does not have an event hub per se, we need to query
        the "EventLogEntry table and send these as Ayon events for processing.

        We try to continue from the last Event processed by the leecher, if
        none is found we start at the moment in time.
        """
        self.log.info("Start listening for Shotgrid Events...")

        last_event_id = None

        while True:
            sg_projects = self.sg_session.find(
                "Project", filters=[["sg_ayon_auto_sync", "is", True]]
            )
            sg_filters = self._build_shotgrid_filters(sg_projects)

            self.log.debug(f"Last Event ID: {last_event_id}")

            if not sg_filters:
                self.log.debug(
                    f"Leecher waiting {self.shotgrid_polling_frequency} "
                    "seconds. No projects with AYON Auto Sync found."
                )
                time.sleep(self.shotgrid_polling_frequency)
                continue

            if last_event_id is None:
                last_event_id = self._get_last_event_processed(sg_filters)

            sg_filters.append(["id", "greater_than", last_event_id])

            self.log.debug(f"Shotgrid filters: {sg_filters}")

            try:
                events = self.sg_session.find(
                    "EventLogEntry",
                    sg_filters,
                    SG_EVENT_QUERY_FIELDS,
                    order=[{"column": "id", "direction": "asc"}],
                    limit=50,
                )

                self.log.debug(f"Found {len(events)} events in Shotgrid.")

                sg_projects_by_id = {
                    sg_project["id"]: sg_project
                    for sg_project in sg_projects
                }
                supported_event_types = []
                if events:
                    supported_event_types = self._get_supported_event_types()

                for event in events:
                    if not event:
                        continue

                    ignore_event = False
                    last_event_id = event["id"]

                    if (
                        event["event_type"].endswith("_Change")
                        and event["attribute_name"].replace("sg_", "")
                        not in self.custom_sg_attribs
                    ):
                        # events related to custom attributes changes
                        # check if event was caused by api user
                        ignore_event = self._is_api_user_event(event)

                    elif event["event_type"] in supported_event_types:
                        # events related to changes in entities we track
                        # check if event was caused by api user
                        ignore_event = self._is_api_user_event(event)

                    if ignore_event:
                        self.log.info(f"Ignoring event: {pformat(event)}")
                        continue

                    self.send_shotgrid_event_to_ayon(event, sg_projects_by_id)

            except Exception:
                self.log.error(traceback.format_exc())

            self.log.debug(
                f"Leecher waiting {self.shotgrid_polling_frequency} seconds..."
            )
            time.sleep(self.shotgrid_polling_frequency)
            continue

    def _is_api_user_event(self, event: dict[str, Any]) -> bool:
        """Check if the event was caused by an API user.

        Args:
            event (dict): The Shotgrid Event data.

        Returns:
            bool: True if the event was caused by an API user.
        """
        # TODO: we have to create specific api user filtering
        if (
            event.get("meta", {}).get("sudo_actual_user", {}).get("type")
            == "ApiUser"
        ):
            return True

    def send_shotgrid_event_to_ayon(
        self, payload: dict[str, Any], sg_projects_by_id: dict[str, Any]
    ):
        """Send the Shotgrid event as an Ayon event.

        Args:
            payload (dict): The Event data.
        """
        description = f"Leeched {payload['event_type']}"
        user_name = payload.get("user", {}).get("name", "Undefined")

        if user_name:
            description = f"Leeched {payload['event_type']} by {user_name}"

        # fix non serializable datetime
        payload["created_at"] = payload["created_at"].isoformat()

        payload_meta = payload.get("meta", {})
        if payload_meta.get("entity_type", "Undefined") == "Project":
            project_name = payload.get("entity", {}).get("name", "Undefined")
            project_id = payload.get("entity", {}).get("id", "Undefined")
        else:
            project_name = payload.get("project", {}).get("name", "Undefined")
            project_id = payload.get("project", {}).get("id", "Undefined")

        sg_project = sg_projects_by_id[project_id]

        ayon_api.dispatch_event(
            "shotgrid.event",
            sender=socket.gethostname(),
            event_hash=payload["id"],
            project_name=project_name,
            username=user_name,
            description=description,
            summary=None,
            payload={
                "action": "shotgrid-event",
                "user_name": user_name,
                "project_name": project_name,
                "project_code": sg_project.get(self.sg_project_code_field),
                "project_code_field": self.sg_project_code_field,
                "sg_payload": payload,
            },
        )

        self.log.info("Dispatched Ayon event with payload:", payload)


def service_main():
    ayon_api.init_service()
    shotgrid_listener = ShotgridListener()
    sys.exit(shotgrid_listener.start_listening())
