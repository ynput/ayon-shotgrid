"""
A AYON Events listener to push changes to Shotgrid.

This service will continually run and query the Ayon Events Server in order to
entroll the events of topic `entity.folder` and `entity.task` when any of the
two are `created`, `renamed` or `deleted`.
"""
# import importlib
import os
import sys
import time
# import types
import signal
import socket

from ayon_shotgrid_hub import AyonShotgridHub

import ayon_api
from ayon_api.entity_hub import EntityHub
from nxtools import logging, log_traceback
import shotgun_api3


class ShotgridTransmitter:
    def __init__(self):
        """ Ensure both Ayon and Shotgrid connections are available.

        Set up common needed attributes and handle shotgrid connection
        closure via signal handlers.

        Args:
            func (Callable, None): In case we want to override the default
                function we cast to the processed events.
        """
        logging.info("Initializing the Shotgrid Transmitter.")

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

            self.ayon_service_user = service_settings["ayon_service_user"]
            if not self.ayon_service_user:
                raise ValueError(
                    "AYON service user not set. Make sure to set it in the "
                    "Addon System settings."
                )

            try:
                self.sg_polling_frequency = int(
                    service_settings["polling_frequency"]
                )
            except Exception:
                self.sg_polling_frequency = 10

        except Exception as e:
            logging.error("Unable to get Addon settings from the server.")
            log_traceback(e)
            raise e

    def start_processing(self):
        """ Main loop querying AYON for `entity.*` events.

        We enroll to events that `created`, `deleted` and `renamed` on AYON `entity`
        to replicate the event in Shotgrid.
        """
        events_we_care = [
            "entity.task.created",
            "entity.task.deleted",
            "entity.task.renamed",
            "entity.task.create",
            "entity.task.attrib_changed",
            "entity.folder.created",
            "entity.folder.deleted",
            "entity.folder.renamed",
            "entity.folder.attrib_changed",
        ]

        logging.debug(
            f"Querying AYON every {self.sg_polling_frequency} seconds for events to "
            "transmit to Shotgrid, and only on Project's that have the attribute "
            "'Shotgrid Push enabled..."
        )

        while True:
            projects_we_care = [
                project["name"]
                for project in ayon_api.get_projects()
                if project.get("attrib", {}).get("shotgridPush", False) is True
            ]

            if not projects_we_care:
                time.sleep(self.sg_polling_frequency)
                continue

            try:
                # Enroll to the events we care about
                event = ayon_api.enroll_event_job(
                    "entity.*",
                    "shotgrid.push",
                    socket.gethostname(),
                    description=(
                        "Handle AYON entity changes and "
                        "sync them to Shotgrid."
                    ),
                    events_filter={
                        "conditions": [
                            {
                                "key": "topic",
                                "value": events_we_care,
                                "operator": "in",
                            },
                            {
                                "key": "user",
                                "value": self.ayon_service_user,
                                "operator": "ne",
                            },
                            {
                                "key": "project",
                                "value": projects_we_care,
                                "operator": "in"
                            }
                        ],
                        "operator": "and",
                    },
                    max_retries=2
                )

                if not event:
                    time.sleep(self.sg_polling_frequency)
                    continue

                source_event = ayon_api.get_event(event["dependsOn"])

                project_name = source_event["project"]
                ay_project = ayon_api.get_project(project_name)

                if not ay_project:
                    # This should never happen since we only fetch events of
                    # projects we have shotgridPush enabled; but just in case
                    # The event happens when after we deleted a project in AYON.
                    logging.error(
                        f"Project {project_name} does not exist in AYON "
                        f"ignoring event {event}."
                    )
                    ayon_api.update_event(
                        event["id"],
                        project_name=project_name,
                        status="finished"
                    )
                    time.sleep(self.sg_polling_frequency)
                    continue

                project_code = ay_project.get("code")

                hub = AyonShotgridHub(
                    project_name,
                    project_code,
                    self.sg_url,
                    self.sg_api_key,
                    self.sg_script_name,
                    sg_project_code_field=self.sg_project_code_field,
                )

                hub.react_to_ayon_event(source_event)

                logging.info("Event has been processed... setting to finished!")
                ayon_api.update_event(
                    event["id"],
                    project_name=project_name,
                    status="finished"
                )
            except Exception as err:
                log_traceback(err)
                ayon_api.update_event(
                    event["id"],
                    project_name=project_name,
                    status="failed"
                )

            time.sleep(self.sg_polling_frequency)
