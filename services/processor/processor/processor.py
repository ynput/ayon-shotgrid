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
IGNORE_TOPICS = {}


class ShotgridProcessor:
    def __init__(self):
        """ Ensure both Ayon and Shotgrid connections are available.

        Set up common needed attributes and handle shotgrid connection
        closure via signal handlers.

        Args:
            func (Callable, None): In case we want to override the default
                function we cast to the processed events.
        """
        logging.info("Initializing the Shotgrid Processor.")

        # Grab all the `handlers` from `processor/handlers` and map them to 
        # the events that are meant to trigger them
        self.handlers_map = None

        try:
            self.settings = ayon_api.get_addon_settings(
                os.environ["AY_ADDON_NAME"],
                os.environ["AY_ADDON_VERSION"]
            )
            self.shotgird_url = self.settings["shotgrid_server"]
            self.shotgrid_script_name = self.settings["shotgrid_script_name"]
            self.shotgrid_api_key = self.settings["shotgrid_api_key"]

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
            self.shotgrid_session = shotgun_api3.Shotgun(
                self.shotgird_url,
                script_name=self.shotgrid_script_name,
                api_key=self.shotgrid_api_key
            )
            self.shotgrid_session.connect()
        except Exception as e:
            logging.error("Unable to connect to Shotgrid Instance:")
            logging.error(e)
            raise e

        signal.signal(signal.SIGINT, self._signal_teardown_handler)
        signal.signal(signal.SIGTERM, self._signal_teardown_handler)

    def _signal_teardown_handler(self, signalnum, frame):
        logging.warning("Process stop requested. Terminating process.")
        self.shotgrid_session.close()
        logging.warning("Termination finished.")
        sys.exit(0)

    def start_processing(self):
        """ Main loop querying the Shotgrid database for new events

        Since Shotgrid does not have an event hub per se, we need to query
        the "EventLogEntry table and send these as Ayon events for processing.
        """

        # Enroll `shotgrid.leech` events
        logging.info("Start enrolling for Ayon `shotgrid.leech` Events...")

        while True:
            logging.info("Querying for new `shotgrid.leech` events...")
            import pprint
            try:
                # while we fix ayon-python-api
                event = ayon_api.enroll_event_job(
                    "shotgrid.leech",
                    "shotgrid.proc",
                    socket.gethostname(),
                    description="Shotgrid Event processing",
                )
                pprint.pprint(event)

                if not event:
                    continue

                event = ayon_api.get_event(event["id"])
                print(event)
                if event["dependsOn"]:
                    previous_event = ayon_api.get_event(event["dependsOn"])
                    print("HENLO?")
                    print(previous_event)
                    # Possible event statuses...
                    # "pending",
                    # "in_progress",
                    # "finished",
                    # "failed",
                    # "aborted",
                    # "restarted",
                    if not previous_event:
                        print("fi")
                        ayon_api.update_event(event["id"], status="aborted")
                        continue

                    if previous_event["status"] in ["in_progress", "restarted"]:
                        # we gotta wait.
                        print("fa")
                        continue
                    elif previous_event["status"] == ["pending", "failed"]:
                        # we retry the previous event
                        print("fu")
                        event = previous_event
                    elif previous_event["status"] == "aborted":
                        print("fe")
                        # dependency has aborted, so we abort this one too
                        ayon_api.update_event(event["id"], status="aborted")

                # If we reach here, means the previous event has finished,
                # so we process
                print("PHEEW")
                pprint.pprint(event)

                if not event["payload"]:
                    # If payload is empty we can't do much...
                    # While `ayon-python-api` is fixed
                    ayon_server_connection = ayon_api.get_server_api_connection()
                    print("BAH")
                    d = {"status": "aborted"}
                    print(d)
                    print(f"events/{event['id']}")
                    response = ayon_server_connection.raw_patch(
                        f"events/{event['id']}",
                        json={"status": "aborted"},
                    )
                    print(response)
                    print("boh")
                    #response.raise_for_status()
                    #ayon_api.update_event(event["id"], status="aborted")


                # 'payload': {'attribute_name': 'code',
                # 'created_at': '2023-01-26T16:30:44+00:00',
                # 'entity': {'id': 23, 'name': 'bunny_010', 'type': 'Sequence'},
                # 'event_type': 'Shotgun_Sequence_Change',
                # 'id': 481509,
                # 'meta': {'attribute_name': 'code',
                #          'entity_id': 23,
                #          'entity_type': 'Sequence',
                #          'field_data_type': 'text',
                #          'new_value': 'bunny_010',
                #          'old_value': 'bunny_010_2',
                #          'type': 'attribute_change'},
                # 'project': {'id': 70,
                #             'name': 'Demo: Animation',
                #             'type': 'Project'},
                # 'session_uuid': '2f49b3d6-9d93-11ed-823f-0242ac110004',
                # 'type': 'EventLogEntry',
                # 'user': {'id': 88, 'name': 'Ayon Ynput', 'type': 'HumanUser'}}
                # events = self.shotgrid_session.find(
                #     "EventLogEntry",
                #     filters,
                #     fields,
                #     order,
                #     limit=50,
                # )


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
        if payload["event_type"] in IGNORE_TOPICS:
            return

        description = f"Leeched {payload['event_type']}"
        user_name = payload.get("user", {}).get("name")

        if user_name:
            description = f"Leeched {payload['event_type']} by {user_name}"

        # fix non serializable datetime
        payload["created_at"] = payload["created_at"].isoformat()

        logging.info(description)

        # while we fix ayon-python-api
        ayon_server_connection = ayon_api.get_server_api_connection()
        # ayon_api.dispatch_event
        ayon_server_connection.dispatch_event(
            "shotgrid.leech",
            sender=socket.gethostname(),
            event_hash=payload["id"],
            project_name=payload.get("project", {}).get("name", "Undefined"),
            username=payload.get("user", {}).get("name", "Undefined"),
            dependencies=payload["id"] - 1,
            description=description,
            summary=None,
            payload=payload,
        )
        logging.info("Dispatched event", payload['event_type'])

        return payload["id"]

