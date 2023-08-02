"""
A Shotgird Events listener processor for Ayon.

This service will continually run and query the Ayon Events Server in orther to
entroll the events of topic `shotgrid.leech` to perform processing of Shotgrid
related events.
"""
import os
import time
import socket

from .lib.ayon_shotgrid_hub import AyonShotgridHub

import ayon_api
from nxtools import logging, log_traceback

SECONDS_BETWEEN_PROCESSING = 5

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

        try:
            self.settings = ayon_api.get_addon_settings(
                os.environ["AYON_ADDON_NAME"],
                os.environ["AYON_ADDON_VERSION"]
            )
            self.shotgird_url = self.settings["shotgrid_server"]
            self.shotgrid_script_name = self.settings["shotgrid_script_name"]
            self.shotgrid_api_key = self.settings["shotgrid_api_key"]

        except Exception as e:
            logging.error("Unable to get Addon settings from the server.")
            log_traceback(e)
            raise e

    def start_processing(self):
        """ Main loop querying the Shotgrid database for new events

        Since Shotgrid does not have an event hub per se, we need to query
        the "EventLogEntry table and send these as Ayon events for processing.
        """

        # Enroll `shotgrid.leech` events
        logging.info("Start enrolling for Ayon `shotgrid.event` Events...")

        while True:
            logging.info("Enroling `shotgrid.event` events every {} seconds...".format(
                SECONDS_BETWEEN_PROCESSING
            ))

            try:
                event = ayon_api.enroll_event_job(
                    "shotgrid.event",
                    "shotgrid.proc",
                    socket.gethostname(),
                    description="Shotgrid Event processing",
                )

                if not event:
                    logging.info("No event of origin `shotgrid.event` is pending.")
                    time.sleep(SECONDS_BETWEEN_PROCESSING)
                    continue

                source_event = ayon_api.get_event(event["dependsOn"])
                payload = source_event["payload"]

                if not payload:
                    time.sleep(SECONDS_BETWEEN_PROCESSING)
                    ayon_api.update_event(event["id"], status="finished")
                    continue

                try:
                    ay_sg_hub = AyonShotgridHub(
                        payload.get("project_name"),
                        payload.get("project_code"),
                        self.shotgird_url,
                        self.shotgrid_api_key,
                        self.shotgrid_script_name,
                    )
                except Exception as e:
                    log_traceback(e)
                    ayon_api.update_event(event["id"], status="failed")

                match payload["action"]:
                    case "create-project":
                        ay_sg_hub.create_project()
                        ay_sg_hub.syncronize_projects(source="shotgrid")

                    case "export-project":
                        ay_sg_hub.create_project()
                        ay_sg_hub.syncronize_projects(source="ayon")

                    case "sync-from-ayon":
                        ay_sg_hub.syncronize_projects(source="ayon")

                    case "sync-from-shotgrid":
                        ay_sg_hub.syncronize_projects(source="shotgrid")

                    case "shotgrid-event":
                        if not payload.get("meta"):
                            time.sleep(SECONDS_BETWEEN_PROCESSING)
                            ayon_api.update_event(event["id"], status="finished")
                            continue

                        ay_sg_hub.react_to_shotgrid_event(payload["meta"])

                logging.info("Event has been processed... setting to finished!")
                ayon_api.update_event(event["id"], status="finished")

            except Exception as e:
                log_traceback(e)

            time.sleep(SECONDS_BETWEEN_PROCESSING)
