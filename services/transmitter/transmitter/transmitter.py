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

from transmitter.lib.constants import CUST_FIELD_CODE_ID, SHOTGRID_ID_ATTRIB, SHOTGRID_TYPE_ATTRIB
from transmitter.lib.utils import get_sg_entity_parent_field

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


        try:
            self.shotgrid_session = shotgun_api3.Shotgun(
                self.shotgird_url,
                script_name=self.shotgrid_script_name,
                api_key=self.shotgrid_api_key
            )
            self.shotgrid_session.connect()
        except Exception as e:
            logging.error("Unable to connect to Shotgrid Instance:")
            log_traceback(e)
            raise e

        signal.signal(signal.SIGINT, self._signal_teardown_handler)
        signal.signal(signal.SIGTERM, self._signal_teardown_handler)

    def _signal_teardown_handler(self, signalnum, frame):
        logging.warning("Process stop requested. Terminating process.")
        self.shotgrid_session.close()
        logging.warning("Termination finished.")
        sys.exit(0)

    def start_processing(self):
        """ Main loop querying AYON for `entity.*` events.

        We enroll to events that `created`, `deleted` and `renamed` on AYON `entity`
        to replicate the event in Shotgrid.
        """
        # This is here till `ayon-python-api` is updated to allow filters when enrolling
        # events.
        events_we_care = [
            "entity.task.created",
            "entity.task.deleted",
            "entity.task.renamed",
            "entity.task.create",
            "entity.folder.created",
            "entity.folder.deleted",
            "entity.folder.renamed",
        ]

        while True:
            logging.info("Querying for new `entity` events...")
            try:
                # TODO: Enroll with a "events_filter" to narrow down the query
                event = ayon_api.enroll_event_job(
                    "entity.*",
                    "shotgrid.push",
                    socket.gethostname(),
                    description="Handle AYON entity changes and sync them to Shotgrid.",
                    events_filter={
                        "conditions": [
                            {
                                "key": "topic",
                                "value": events_we_care,
                                "operator": "in",
                            },
                        ],
                        "operator": "and",
                    }
                )

                if not event:
                    logging.info("No event of origin `entity.*` is pending.")
                    time.sleep(1.5)
                    continue

                source_event = ayon_api.get_event(event["dependsOn"])
                event_id = event["id"]

                ay_id = source_event["summary"]["entityId"]
                project_name = source_event["project"]
                entity_hub = EntityHub(project_name)

                try:
                    entity_hub.project_entity
                except ValueError:
                    logging.error(f"Project {project_name} does not exist in Ayon. This might be cause the project was deleted before all the events were processed.")
                    ayon_api.update_event(event_id, project_name=project_name, status="finished")
                    time.sleep(1.5)
                    continue

                entity_hub.query_entities_from_server()
                ay_entity = entity_hub.get_entity_by_id(ay_id)

                ay_project = ayon_api.get_project(project_name)

                project_name = source_event["project"]

                entity_hub = EntityHub(project_name)
                entity_hub.query_entities_from_server()
                ay_entity = entity_hub.get_entity_by_id(ay_id)

                ay_project = ayon_api.get_project(project_name)
                sg_project_id = ay_project["attrib"]["shotgridId"]

                if not sg_project_id:
                    logging.error("AYON is missing the Shotgrid Project ID.")
                    ayon_api.update_event(event_id, project_name=project_name, status="failed")
                    time.sleep(1.5)
                    continue

                sg_project = self.shotgrid_session.find_one(
                    "Project",
                    [["id", "is", int(sg_project_id)]]
                )

                if not sg_project:
                    logging.error(
                        f"Project '{project_name} <{sg_project_id}>' not in Shotgrid?"
                    )
                    ayon_api.update_event(event_id, project_name=project_name, status="finished")
                    time.sleep(1.5)
                    continue

                if not ay_entity:
                    logging.error(f"Event has a non existant entity? {ay_id}")
                    ayon_api.update_event(event_id, project_name=project_name, status="failed")
                    time.sleep(1.5)
                    continue

                sg_id = ay_entity.attribs.get("shotgridId")
                sg_type = ay_entity.attribs.get("shotgridType")

                if sg_id and sg_type:
                    sg_entity = self.shotgrid_session.find_one(sg_type, [["id", "is", int(sg_id)]])

                match source_event["topic"]:
                    case "entity.task.created" | "entity.folder.created":
                        if sg_entity:
                            logging.warning(f"Entity {sg_entity} already exists in Shotgrid!")
                            ayon_api.update_event(event_id, project_name=project_name, status="finished")
                            time.sleep(1.5)
                            continue

                        if ay_entity.entity_type == "task":
                            sg_type = "Task"
                        else:
                            sg_type = ay_entity.folder_type

                        try:
                            sg_entity = self._create_sg_entity(
                                ay_entity,
                                sg_project,
                                sg_type
                            )
                            logging.info(f"Created Shotgrid entity: {sg_entity}")

                            ay_entity.attribs.set(
                                SHOTGRID_ID_ATTRIB,
                                sg_entity["id"]
                            )
                            ay_entity.attribs.set(
                                SHOTGRID_TYPE_ATTRIB,
                                sg_entity["type"]
                            )
                            entity_hub.commit_changes()
                        except Exception as e:
                            logging.error(f"Unable to create {sg_type} <{ay_id}> in Shotgrid!")
                            log_traceback(e)
                            ayon_api.update_event(event_id, project_name=project_name, status="failed")
                            continue

                    case "entity.task.deleted" | "entity.folder.deleted":
                        try:
                            self._delete_sg_entity(sg_type, sg_id)
                            logging.info(f"Retired Shotgrid entity: {sg_type} <{sg_id}>")
                        except Exception as e:
                            logging.error(f"Unable to delete {sg_type} <{sg_id}> in Shotgrid!")
                            log_traceback(e)
                            ayon_api.update_event(event_id, project_name=project_name, status="failed")
                            continue

                    case "entity.task.renamed" | "entity.folder.renamed":
                        try:
                            sg_entity = self._update_sg_entity(sg_type, sg_id, ay_entity)
                            logging.info(f"Updated Shotgrid entity: {sg_entity}")
                        except Exception as e:
                            logging.error(f"Unable to delete {sg_type} <{sg_id}> in Shotgrid!")
                            log_traceback(e)
                            ayon_api.update_event(event_id, project_name=project_name, status="failed")
                            continue

                logging.info("Event has been processed... setting to finished!")
                ayon_api.update_event(event["id"], project_name=project_name, status="finished")
            except Exception as err:
                log_traceback(err)

            time.sleep(1.5)

    def _create_sg_entity(
        self,
        ay_entity,
        sg_project,
        sg_type,
    ):
        """ Create a new Shotgrid entity.

        Args:
            ay_entity (dict): The AYON entity.
            sg_project (dict): The Shotgrid Project.
            sg_type (str): The Shotgrid type of the new entity.
            sg_name (str): The name of the new entity.
        """
        sg_field_name = "code"

        if ay_entity.entity_type == "task":
            sg_field_name = "content"

        sg_parent_id = ay_entity.parent.attribs.get(SHOTGRID_ID_ATTRIB)
        sg_parent_type = ay_entity.parent.attribs.get(SHOTGRID_TYPE_ATTRIB)

        if not (sg_parent_id and sg_parent_type):
            logging.error("Parent does not exist in Shotgird!")
            #create parent ?
            return

        parent_field = get_sg_entity_parent_field(
            self.shotgrid_session,
            sg_project,
            sg_parent_type,
        )

        data = {
            "project": sg_project,
            parent_field: {"type": sg_parent_type, "id": int(sg_parent_id)},
            sg_field_name: ay_entity.name,
            CUST_FIELD_CODE_ID: ay_entity.id,
        }

        return self.shotgrid_session.create(sg_type, data)

    def _delete_sg_entity(self, sg_type, sg_id):
        return self.shotgrid_session.delete(sg_type, sg_id)

    def _update_sg_entity(self, sg_type, sg_id, ay_entity):
        # We currently only track the name...
        sg_field_name = "code"

        if ay_entity.get("taskType"):
            sg_field_name = "content"

        return self.shotgrid_session.update(
            sg_type,
            sg_id,
            {
                sg_field_name: ay_entity["name"],
                CUST_FIELD_CODE_ID: ay_entity["id"]
            }
        )

