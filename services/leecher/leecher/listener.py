"""
A Shotgird Events listener leecher for Ayon.

This service will continually run and query the EventLogEntry table from
Shotgrid and converts them to Ayon events, and can be configured from the Ayon
Addon settings page.
"""
import os
import sys
import time
import signal
import socket
from typing import Any, Callable, Union

from constants import (
    AYON_SHOTGRID_ENTITY_TYPE_MAP,
    SG_EVENT_CHANGE_ATTR_FIELDS,
    SG_EVENT_TYPES,
    SG_EVENT_QUERY_FIELDS
)

import ayon_api
from nxtools import logging, log_traceback
import shotgun_api3


class ShotgridListener:
    def __init__(self, func: Union[Callable, None] = None):
        """ Ensure both Ayon and Shotgrid connections are available.

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
            self.sg_url = self.settings["shotgrid_server"]
            self.sg_project_code_field = self.settings["shotgrid_project_code_field"]

            shotgrid_secret = ayon_api.get_secret(self.settings["shotgrid_script_name"])
            self.sg_script_name = shotgrid_secret.get("name")
            self.sg_api_key = shotgrid_secret.get("value")

            try:
                self.shotgrid_polling_frequency = int(
                    self.settings["service_settings"]["polling_frequency"]
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

        We want to filter out all the Events in the SG database that do not meet
        our needs:
            1) Events of Projects with "AYON Auto Sync" enabled.
            2) Events on entities and type for entities we track.

        Returns:
            filters (list): Filter to apply to the SG query.
        """
        filters = []

        sg_projects = self.sg_session.find(
            "Project",
            filters=[["sg_ayon_auto_sync", "is", True]]
        )
        logging.debug(f"Projects with the autosync enabled {sg_projects}")

        filters.append(["project", "in", sg_projects])

        sg_event_types = []

        # TODO: Create a complex filter so skip event types "_Change" that
        # we don't handle.
        for entity_type in AYON_SHOTGRID_ENTITY_TYPE_MAP.keys():
            for event_name in SG_EVENT_TYPES:
                sg_event_types.append(event_name.format(entity_type))

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
            topics=["shotgrid.leech"],
            fields=["hash"]
        ):
            last_event_id = int(last_event_id["hash"])

        if not last_event_id:
            last_event = self.sg_session.find_one(
                "EventLogEntry",
                filters=sg_filters,
                fields=["id", "project"],
                order=[{"column": "id", "direction": "desc"}]
            )
            last_event_id = last_event["id"]

        logging.debug(f"Last non-processed SG Event is {last_event}")

        return last_event_id

    def start_listening(self):
        """ Main loop querying the Shotgrid database for new events

        Since Shotgrid does not have an event hub per se, we need to query
        the "EventLogEntry table and send these as Ayon events for processing.

        We try to continue from the last Event processed by the leecher, if none
        is found we start at the moment in time.
        """
        logging.info("Start listening for Shotgrid Events...")

        sg_filters = self._build_shotgrid_filters()
        last_event_id = self._get_last_event_processed(sg_filters)

        while True:
            sg_filters = self._build_shotgrid_filters()
            sg_filters.append(
                ["id", "greater_than", last_event_id]
            )

            try:
                events = self.sg_session.find(
                    "EventLogEntry",
                    sg_filters,
                    SG_EVENT_QUERY_FIELDS,
                    order=[{"column": "id", "direction": "asc"}],
                    limit=50,
                )

                if not events:
                    logging.info("No new events found.")
                    logging.info(
                        f"Waiting {self.shotgrid_polling_frequency} seconds..."
                    )
                    time.sleep(self.shotgrid_polling_frequency)
                    continue


                logging.info(f"Found {len(events)} events in Shotgrid.")

                for event in events:
                    if not event:
                        continue

                    if (
                        event["event_type"].endswith("_Change") and
                        event["attribute_name"] not in SG_EVENT_CHANGE_ATTR_FIELDS
                    ):
                        # Skip change events we cannot handle yet...
                        continue

                    last_event_id = self.func(event)

            except Exception as err:
                logging.error(err)
                log_traceback(err)

            logging.info(
                f"Waiting {self.shotgrid_polling_frequency} seconds..."
            )
            time.sleep(self.shotgrid_polling_frequency)

    def send_shotgrid_event_to_ayon(self, payload: dict[str, Any]) -> int:
        """ Send the Shotgrid event as an Ayon event.

        Args:
            payload (dict): The Event data.

        Returns:
            int: The Shotgrid Event ID.
        """
        logging.info(f"Processing Shotgrid Event {payload}")
        description = f"Leeched {payload['event_type']}"
        user_name = payload.get("user", {}).get("name", "Undefined")

        if user_name:
            description = f"Leeched {payload['event_type']} by {user_name}"

        # fix non serializable datetime
        payload["created_at"] = payload["created_at"].isoformat()

        logging.info(description)

        if payload.get("meta", {}).get("entity_type", "Undefined") == "Project":
            project_name = payload.get("entity", {}).get("name", "Undefined")
            project_id = payload.get("entity", {}).get("id", "Undefined")
        else:
            project_name = payload.get("project", {}).get("name", "Undefined")
            project_id = payload.get("project", {}).get("id", "Undefined")

        logging.info(f"Event is from Project {project_name} ({project_id})")

        sg_project = self.sg_session.find_one(
            "Project",
            [["id", "is", project_id]],
            fields=[self.sg_project_code_field]
        )
        logging.debug(f"Found Shotgrid Project {sg_project}")

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
                "sg_payload": payload,
            }
        )

        logging.info("Dispatched Ayon event ", payload['event_type'])

        return payload["id"]

