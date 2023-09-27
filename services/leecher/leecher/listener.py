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

import ayon_api
from nxtools import logging
import shotgun_api3


# Probably could allow this to be configured via the Addon settings
# And do a query where we alread filter these out.
# Clearly not working, since these are ftrack specific ones.
ENTITIES_TO_TRACK = [
    "Project",
    "Sequence",
    "Shot",
    "Task",
    "Asset",
]

EVENT_TYPES = [
    "Shotgun_{0}_New",  # a new entity was created.
    "Shotgun_{0}_Change",  # an entity was modified.
    "Shotgun_{0}_Retirement",  # an entity was deleted.
    "Shotgun_{0}_Revival",  # an entity was revived.
]

# To be revised once we usin links
IGNORE_ATTRIBUTE_NAMES = [
    "assets",
    "parent_shots",
    "retirement_date",
    "shots"
]


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
            self.sg_leechable_projects = self.settings["service_settings"]["projects_to_leech"]
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
            logging.error(e)

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
            logging.error(e)
            raise e

        signal.signal(signal.SIGINT, self._signal_teardown_handler)
        signal.signal(signal.SIGTERM, self._signal_teardown_handler)

    def _signal_teardown_handler(self, signalnum, frame):
        logging.warning("Process stop requested. Terminating process.")
        self.sg_session.close()
        logging.warning("Termination finished.")
        sys.exit(0)

    def _get_valid_events(self):
        """Helper method to create the Shotgird Query filter.

        Iterate over the allowed entities types and event types and return
        a list of all premutations.
        """
        valid_events = []

        for entity_type in ENTITIES_TO_TRACK:
            for event_name in EVENT_TYPES:
                valid_events.append(event_name.format(entity_type))

        return valid_events

    def start_listening(self):
        """ Main loop querying the Shotgrid database for new events

        Since Shotgrid does not have an event hub per se, we need to query
        the "EventLogEntry table and send these as Ayon events for processing.
        """
        logging.info("Start listening for Shotgrid Events...")
        fields = [
            "id",
            "event_type",
            "attribute_name",
            "meta",
            "entity",
            "user",
            "project",
            "session_uuid",
            "created_at",
        ]
        order = [{"column": "id", "direction": "asc"}]

        last_event_id = None
        for last_event_id in ayon_api.get_events(
            topics=["shotgrid.leech"],
            fields=["hash"]
        ):
            last_event_id = int(last_event_id["hash"])

        event_type_filters = [
            ["event_type", "is", event_type]
            for event_type in self._get_valid_events()
        ]

        sg_projects = self.sg_session.find(
            "Project",
            filters=[{
                "filter_operator": "any",
                "filters": [
                    [f"{self.sg_project_code_field}", "is", project_code.strip()]
                    for project_code in self.sg_leechable_projects.split(",")
                ]
            }]
        )

        projects_filters = [
            ["project", "is", project]
            for project in sg_projects
        ]

        shotgrid_events_filter = {
            "filter_operator": "any",
            "filters": event_type_filters + projects_filters
        }

        if not last_event_id:
            last_event_id = self.sg_session.find_one(
                "EventLogEntry",
                filters=[shotgrid_events_filter],
                fields=["id"],
                order=[{"column": "id", "direction": "desc"}]
            )["id"]

        while True:
            logging.info(f"Last Event ID is {last_event_id}")
            logging.info("Querying for new events since the last one...")
            filters = None
            filters = [
                ["id", "greater_than", last_event_id],
                shotgrid_events_filter
            ]

            try:
                events = self.sg_session.find(
                    "EventLogEntry",
                    filters,
                    fields,
                    order,
                    limit=50,
                )
                if events:
                    logging.info(f"Query returned {len(events)} events.")

                    for event in events:
                        if not event:
                            continue

                        if event.get("attribute_name") in IGNORE_ATTRIBUTE_NAMES:
                            continue

                        last_event_id = self.func(event)
                else:
                    logging.info("No new events found.")

            except Exception as err:
                logging.error(err)

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
        logging.info("Processing Shotgrid Event")

        description = f"Leeched {payload['event_type']}"
        user_name = payload.get("user", {}).get("name", "Undefined")

        if user_name:
            description = f"Leeched {payload['event_type']} by {user_name}"

        # fix non serializable datetime
        payload["created_at"] = payload["created_at"].isoformat()

        logging.info(description)
        project_name = payload.get("project", {}).get("name", "Undefined")
        project_id = payload.get("project", {}).get("id", "Undefined")

        logging.info(f"Event is from Project {project_name} ({project_id})")

        sg_project = self.sg_session.find_one(
            "Project",
            [["id", "is", project_id]],
            fields=[self.sg_project_code_field]
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
                "sg_payload": payload,
            }
        )

        logging.info("Dispatched Ayon event ", payload['event_type'])

        return payload["id"]

