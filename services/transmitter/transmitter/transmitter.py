"""
A AYON Events listener to push changes to Shotgrid.

This service will continually run and query the AYON Events Server in order to
enroll the events of topic `entity.folder` and `entity.task` when any of the
two are `created`, `renamed` or `deleted`.
"""
import sys
import time
from datetime import datetime
import socket
import traceback

import ayon_api
import shotgun_api3

from ayon_shotgrid_hub import AyonShotgridHub

from utils import get_logger


COMMENTS_SYNC_SECS_INTERVAL = 15
COMMENTS_SYNC_TIMEOUT = 60 * 2


class ShotgridTransmitter:
    log = get_logger(__file__)
    _sg: shotgun_api3.Shotgun = None

    def __init__(self):
        """ Ensure both AYON and Shotgrid connections are available.

        Set up common needed attributes and handle shotgrid connection
        closure via signal handlers.

        Args:
            func (Callable, None): In case we want to override the default
                function we cast to the processed events.
        """
        self.log.info("Initializing the Shotgrid Transmitter.")

        self._cached_hubs = {}
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

            # Compatibility settings
            custom_attribs_map = self.settings["compatibility_settings"][
                "custom_attribs_map"]
            self.custom_attribs_map = {
                attr["ayon"]: attr["sg"]
                for attr in custom_attribs_map
                if attr["sg"]
            }
            self.custom_attribs_map.update({
                "status": "status_list",
                "tags": "tags",
                "assignees": "task_assignees"
            })

            self.custom_attribs_types = {
                attr["sg"]: (attr["type"], attr["scope"])
                for attr in custom_attribs_map
                if attr["sg"]
            }
            self.sg_enabled_entities = (
                self.settings["compatibility_settings"]
                             ["shotgrid_enabled_entities"])
            try:
                self.sg_polling_frequency = int(
                    service_settings["polling_frequency"]
                )
            except Exception:
                self.sg_polling_frequency = 10

        except Exception as e:
            self.log.error("Unable to get Addon settings from the server.")
            raise e

    def get_sg_connection(self):
        """Ensure we can talk to AYON and Shotgrid.

        Start connections to the APIs and catch any possible error, we abort if
        this steps fails for any reason.
        """

        if self._sg is None:
            try:
                self._sg = shotgun_api3.Shotgun(
                    self.sg_url,
                    script_name=self.sg_script_name,
                    api_key=self.sg_api_key,
                )
            except Exception as e:
                self.log.error("Unable to create Shotgrid Session.")
                raise e

        try:
            self._sg.connect()

        except Exception as e:
            self.log.error("Unable to connect to Shotgrid.")
            raise e

        return self._sg

    def start_processing(self):
        """ Main loop querying AYON for `entity.*` events.

        We enroll to events that `created`, `deleted` and `renamed`
        on AYON `entity` to replicate the event in Shotgrid.
        """
        events_we_care = [
            "entity.task.created",
            "entity.task.deleted",
            "entity.task.renamed",
            "entity.task.create",
            "entity.task.assignees_changed",
            "entity.task.attrib_changed",
            "entity.task.status_changed",
            "entity.task.tags_changed",
            "entity.folder.created",
            "entity.folder.deleted",
            "entity.folder.renamed",
            "entity.folder.attrib_changed",
            "entity.folder.status_changed",
            "entity.folder.tags_changed",
            "entity.version.status_changed",
        ]

        last_comments_sync = datetime.min
        while True:
            try:
                # get all service users
                service_users = [
                    user["name"]
                    for user in ayon_api.get_users(
                        fields={"accessGroups", "isService", "name"})
                    if user["isService"]
                ]

                # Run comments sync
                now_time = datetime.now()
                sec_diff = (now_time - last_comments_sync).total_seconds()
                if sec_diff > COMMENTS_SYNC_SECS_INTERVAL:
                    project_names = self._get_sync_project_names()
                    for project_name in project_names:
                        hub = self._get_hub(project_name)
                        hub.sync_comments(last_comments_sync)
                    last_comments_sync = now_time

                # enrolling only events which were not created by any
                # of service users so loopback is avoided
                event = ayon_api.enroll_event_job(
                    events_we_care,
                    "shotgrid.push",
                    socket.gethostname(),
                    ignore_sender_types=["shotgrid"],
                    description=(
                        "Handle AYON entity changes and "
                        "sync them to Shotgrid."
                    ),
                    max_retries=2
                )

                if not event:
                    time.sleep(self.sg_polling_frequency)
                    continue

                source_event = ayon_api.get_event(event["dependsOn"])

                project_name = source_event["project"]

                if project_name in self._get_sync_project_names():
                    # This should never happen since we only fetch events of
                    # projects we have shotgridPush enabled; but just in case
                    # The event happens when after we deleted a project in
                    # AYON.
                    self.log.info(
                        f"Project {project_name} does not exist in AYON "
                        "or does not have the `shotgridPush` attribute set, "
                        f"ignoring event {event}."
                    )
                    ayon_api.update_event(
                        event["id"],
                        project_name=project_name,
                        status="finished"
                    )
                    continue

                hub = self._get_hub(project_name)
                hub.react_to_ayon_event(source_event)

                self.log.info("Event has been processed... setting to finished!")
                ayon_api.update_event(
                    event["id"],
                    project_name=project_name,
                    status="finished"
                )
            except Exception:
                self.log.error(
                    "Error processing event", exc_info=True)

                ayon_api.update_event(
                    event["id"],
                    project_name=project_name,
                    status="failed",
                    payload={
                        "message": traceback.format_exc(),
                    },
                )

    def _get_sync_project_names(self):
        """Get project names that are enabled for SG sync."""
        ayon_projects = ayon_api.get_projects(fields=["name", "attrib"])

        project_names = []
        for project in ayon_projects:
            if project["attrib"].get("shotgridPush"):
                project_names.append(project["name"])

        return project_names

    def _get_hub(self, project_name):
        hub = self._cached_hubs.get(project_name)

        if not hub:
            ay_project = ayon_api.get_project(project_name)
            project_code = ay_project["code"]
            hub = AyonShotgridHub(
                self.get_sg_connection(),
                project_name,
                project_code,
                sg_project_code_field=self.sg_project_code_field,
                custom_attribs_map=self.custom_attribs_map,
                custom_attribs_types=self.custom_attribs_types,
                sg_enabled_entities=self.sg_enabled_entities,
            )
            self._cached_hubs[project_name] = hub

        return hub


def service_main():
    ayon_api.init_service()
    shotgrid_transmitter = ShotgridTransmitter()
    sys.exit(shotgrid_transmitter.start_processing())
