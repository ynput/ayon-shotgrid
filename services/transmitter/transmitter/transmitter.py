"""
A AYON Events listener to push changes to Shotgrid.

This service will continually run and query the AYON Events Server in order to
enroll the events of topic `entity.folder` and `entity.task` when any of the
two are `created`, `renamed` or `deleted`.
"""
import sys
import time
from datetime import datetime, timezone, timedelta
import socket
import traceback

import arrow

import ayon_api
import shotgun_api3

from ayon_shotgrid_hub import AyonShotgridHub
from constants import (
    COMMENTS_SYNC_TIMEOUT,
    SHOTGRID_COMMENTS_TOPIC,
    COMMENTS_SYNC_INTERVAL
)

from utils import get_logger


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

        last_comments_sync = datetime.min.replace(tzinfo=timezone.utc)
        while True:
            try:
                # Run comments sync
                now_time = arrow.utcnow()
                sec_diff = (now_time - last_comments_sync).total_seconds()
                if sec_diff > COMMENTS_SYNC_INTERVAL:
                    self._sync_comments()

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

                if project_name not in self._get_sync_project_names():
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

    def _sync_comments(self):
        """Checks if no other syncing is runnin or when last successful ran."""
        any_in_progress = self._cleanup_in_progress_comment_events()
        if any_in_progress:
            return

        now = arrow.utcnow()
        activities_after_date = None

        last_finished_event = self._get_last_finished_event()
        if last_finished_event is not None:
            created_at = arrow.get(
                last_finished_event["createdAt"]
            ).to("local")
            delta = now - created_at
            if delta.seconds < COMMENTS_SYNC_INTERVAL:
                return
            activities_after_date = created_at

        if activities_after_date is None:
            activities_after_date = now - timedelta(days=5)

        response = ayon_api.dispatch_event(
            SHOTGRID_COMMENTS_TOPIC,
            description=(
                "Synchronizing comments from ftrack to AYON."
            ),
            summary=None,
            payload={},
            finished=True,
            store=True,
        )
        if isinstance(response, str):
            event_id = response
        else:
            event_id = response["id"]

        try:
            synced_comments = 0
            project_names = self._get_sync_project_names()
            for project_name in project_names:
                hub = self._get_hub(project_name)
                synced_comments += hub.sync_comments(activities_after_date)
            success = True
        except Exception:
            success = False
            self._log.warning("Failed to sync comments.", exc_info=True)

        finally:
            ayon_api.update_event(
                event_id,
                description="Synchronized comments from AYON to SG.",
                status="finished" if success else "failed",
                payload={"synced_comments": synced_comments},
            )

    def _cleanup_in_progress_comment_events(self) -> bool:
        """Clean stuck or hard failed synchronizations"""
        in_progress_events = list(ayon_api.get_events(
            topics={SHOTGRID_COMMENTS_TOPIC},
            statuses={"in_progress"},
            fields={"id", "createdAt"}
        ))

        any_in_progress = False
        now = arrow.utcnow()
        for event in in_progress_events:
            created_at = arrow.get(event["createdAt"]).to("local")
            delta = now - created_at
            if delta.seconds < COMMENTS_SYNC_TIMEOUT:
                any_in_progress = True
            else:
                ayon_api.update_event(
                    event["id"],
                    status="failed",
                )
        return any_in_progress

    def _get_last_finished_event(self):
        """Finds last successful run of comments synching to SG."""
        finished_events = list(ayon_api.get_events(
            topics={SHOTGRID_COMMENTS_TOPIC},
            statuses={"finished"},
            limit=1,
            order=ayon_api.SortOrder.descending,
        ))
        for event in finished_events:
            return event
        return None


def service_main():
    ayon_api.init_service()
    shotgrid_transmitter = ShotgridTransmitter()
    sys.exit(shotgrid_transmitter.start_processing())
