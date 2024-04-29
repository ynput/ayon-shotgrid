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
from typing import Any, Callable, Union
from nxtools import logging, log_traceback

from constants import (
    SG_EVENT_TYPES,
    SG_EVENT_QUERY_FIELDS,
)

import ayon_api
import shotgun_api3


class ShotgridListener:
    def __init__(self, func: Union[Callable, None] = None):
        """Ensure both Ayon and Shotgrid connections are available.

        Set up common needed attributes and handle shotgrid connection
        closure via signal handlers.

        Args:
            func (Callable, None): In case we want to override the default
                function we cast to the processed events.
        """
        logging.info("Initializing the Shotgrid Listener.")
        if func is None:
            self.func = self.send_shotgrid_event_to_ayon
        else:
            self.func = func

        logging.debug(f"Callback method is {self.func}.")

        try:
            ayon_api.init_service()
            self.settings = ayon_api.get_service_addon_settings()
            service_settings = self.settings["service_settings"]

            self.sg_url = self.settings["shotgrid_server"]
            self.sg_project_code_field = self.settings[
                "shotgrid_project_code_field"]

            # get server op related ShotGrid script api properties
            shotgrid_secret = ayon_api.get_secret(
                service_settings["script_key"])
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

            # TODO: implement a way to handle status_list and tags
            # self.custom_attribs_map.update({
            #     "status": "status_list",
            #     "tags": "tags"
            # })

            self.sg_enabled_entities = self.settings["compatibility_settings"]["shotgrid_enabled_entities"]  # noqa: E501

            try:
                self.shotgrid_polling_frequency = int(
                    service_settings["polling_frequency"]
                )
            except Exception:
                self.shotgrid_polling_frequency = 10

        except Exception as e:
            logging.error("Unable to get Addon settings from the server.")
            log_traceback(e)
            raise e

        try:
            self.sg_session = shotgun_api3.Shotgun(
                self.sg_url,
                script_name=self.sg_script_name,
                api_key=self.sg_api_key
            )
            self.sg_session.connect()
        except Exception as e:
            logging.error("Unable to connect to Shotgrid Instance:")
            log_traceback(e)
            raise e

        signal.signal(signal.SIGINT, self._signal_teardown_handler)
        signal.signal(signal.SIGTERM, self._signal_teardown_handler)

    def _signal_teardown_handler(self, signalnum, frame):
        logging.warning("Process stop requested. Terminating process.")
        self.sg_session.close()
        logging.warning("Termination finished.")
        sys.exit(0)

    def _build_shotgrid_filters(self):
        """Build SG filters for Events query.

        We want to filter out all the Events in the SG database that do not
        meet our needs:
            1) Events of Projects with "AYON Auto Sync" enabled.
            2) Events on entities and type for entities we track.

        Returns:
            filters (list): Filter to apply to the SG query.
        """
        filters = []

        sg_projects = self.sg_session.find(
            "Project", filters=[["sg_ayon_auto_sync", "is", True]]
        )

        if not sg_projects:
            return []

        filters.append(["project", "in", sg_projects])

        sg_event_types = []

        # TODO: Create a complex filter so skip event types "_Change" that
        # we don't handle.
        for entity_type in self.sg_enabled_entities:
            for event_name in SG_EVENT_TYPES:
                sg_event_types.append(event_name.format(entity_type))

        if sg_event_types:
            filters.append(["event_type", "in", sg_event_types])

        return filters

    def _get_last_event_processed(self, sg_filters):
        """Find the Event ID for the last SG processed event.

        First attempt to find it via AYON, if none is found we get the last
        matching event from Shotgrid.

        Returns:
            last_event_id (int): The last known Event id.
        """
        last_event_id = None

        for last_event_id in ayon_api.get_events(
            topics=["shotgrid.leech"], fields=["hash"]
        ):
            last_event_id = int(last_event_id["hash"])

        if not last_event_id:
            last_event = self.sg_session.find_one(
                "EventLogEntry",
                filters=sg_filters,
                fields=["id", "project"],
                order=[{"column": "id", "direction": "desc"}],
            )
            last_event_id = last_event["id"]

        logging.debug(f"Last non-processed SG Event is {last_event}")

        return last_event_id

    def start_listening(self):
        """Main loop querying the Shotgrid database for new events

        Since Shotgrid does not have an event hub per se, we need to query
        the "EventLogEntry table and send these as Ayon events for processing.

        We try to continue from the last Event processed by the leecher, if
        none is found we start at the moment in time.
        """
        logging.info("Start listening for Shotgrid Events...")

        sg_filters = self._build_shotgrid_filters()
        last_event_id = self._get_last_event_processed(sg_filters)

        while True:
            sg_filters = self._build_shotgrid_filters()
            if not sg_filters:
                time.sleep(self.shotgrid_polling_frequency)
                continue

            sg_filters.append(["id", "greater_than", last_event_id])

            try:
                events = self.sg_session.find(
                    "EventLogEntry",
                    sg_filters,
                    SG_EVENT_QUERY_FIELDS,
                    order=[{"column": "id", "direction": "asc"}],
                    limit=50,
                )

                if not events:
                    time.sleep(self.shotgrid_polling_frequency)
                    continue

                logging.info(f"Found {len(events)} events in Shotgrid.")

                for event in events:
                    if not event:
                        continue

                    # Filter out events we do not know how to handle
                    if (
                        event["event_type"].endswith("_Change")
                        and event["attribute_name"].replace("sg_", "") not in list(self.custom_attribs_map.values())
                    ):
                        logging.debug(f"Skipping event for attribute change '{event['attribute_name'].replace('sg_', '')}', as we can't handle it.")
                        last_event_id = event.get("id", None)
                        continue

                    last_event_id = self.func(event)

            except Exception as err:
                logging.error(err)
                log_traceback(err)

            time.sleep(self.shotgrid_polling_frequency)

    def send_shotgrid_event_to_ayon(self, payload: dict[str, Any]) -> int:
        """Send the Shotgrid event as an Ayon event.

        Args:
            payload (dict): The Event data.

        Returns:
            int: The Shotgrid Event ID.
        """
        description = f"Leeched {payload['event_type']}"
        user_name = payload.get("user", {}).get("name", "Undefined")

        if user_name:
            description = f"Leeched {payload['event_type']} by {user_name}"

        # fix non serializable datetime
        payload["created_at"] = payload["created_at"].isoformat()

        if payload.get("meta", {}).get("entity_type", "Undefined") == "Project":
            project_name = payload.get("entity", {}).get("name", "Undefined")
            project_id = payload.get("entity", {}).get("id", "Undefined")
        else:
            project_name = payload.get("project", {}).get("name", "Undefined")
            project_id = payload.get("project", {}).get("id", "Undefined")

        sg_project = self.sg_session.find_one(
            "Project", [["id", "is", project_id]], fields=[self.sg_project_code_field]
        )

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

        logging.info("Dispatched Ayon event with payload:", payload)

        return payload["id"]
