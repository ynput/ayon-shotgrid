import collections
import time
import logging

from ayon_api.entity_hub import EntityHub
from ayon_api.utils import slugify_string
from ayon_api import (
    create_project,
    get_project,
)

from .constants import (
    CUST_FIELD_CODE_ID,
    CUST_FIELD_CODE_SYNC,
    SHOTGRID_ID_ATTRIB,
    SHOTGRID_TYPE_ATTRIB,
)

from .utils import (
    get_sg_entities,
    get_sg_missing_ay_attributes,
    get_sg_project_by_name,
    create_sg_entities_in_ay,
)


class IdsMapping(object):
    def __init__(self):
        self._shotgrid_to_server = {}
        self._server_to_shotgrid = {}

    def set_shotgrid_to_server(self, shotgrid_id, server_id):
        self._shotgrid_to_server[shotgrid_id] = server_id
        self._server_to_shotgrid[server_id] = shotgrid_id

    def set_server_to_shotgrid(self, server_id, shotgrid_id):
        self.set_shotgrid_to_server(shotgrid_id, server_id)

    def get_server_mapping(self, shotgrid_id):
        return self._shotgrid_to_server.get(shotgrid_id)

    def get_shotgrid_mapping(self, server_id):
        return self._server_to_shotgrid.get(server_id)


class SyncFromShotgrid:
    """Helper for sync project from Shotgrid."""

    def __init__(self, session, project_name, log=None):
        self._log = log
        self._sg_session = session

        self._ay_project = get_project(project_name)
        if not self._ay_project:
            msg = (
                f"Project {project_name} does not exist in Ayon,"
                "import it at the 'Ayon > Settings > Shotgrid Sync' tab."
            )
            self.log.error(msg)
            raise ValueError(msg)

        self._entity_hub = EntityHub(project_name)

        self._sg_project = get_sg_project_by_name(
            self._sg_session,
            project_name
        )
        self._check_shotgrid_project()

        self._sg_entities_by_id = {}
        self._sg_entities_by_parent_id = {}

        self._ids_mapping = IdsMapping()
        self._ids_mapping.set_shotgrid_to_server(
            self._sg_project["id"],
            self._ay_project["name"],
        )

    @property
    def log(self):
        if self._log is None:
            self._log = logging.getLogger(self.__class__.__name__)
        return self._log

    def _check_shotgrid_project(self):
        """ Ensure Shotgrid project exists and has all required fields.
        """
        self.log.info("Ensuring Shotgrid Project has all the required fields.")

        missing_attrs = get_sg_missing_ay_attributes(self._sg_session)

        if missing_attrs:
            msg = (f"Shotgrid is missing attributes: {missing_attrs}")
            self.log.warning(msg)
            raise ValueError(msg)

    def sync_to_ayon(self, preset_name=None):
        self.log.info("Started Ayon Syncronization with Shotgrid.")
        self.log.info(f"Project Name: {self._ay_project['name']}")

        sync_start_time = time.perf_counter()
        self.log.info("Loading Entities data from Ayon.")
        self._entity_hub.query_entities_from_server()
        sync_step_time = time.perf_counter()
        self.log.info(
            f"Populating the EntitHub took {sync_step_time - sync_start_time}."
        )

        self.log.info("Adding Shotgrid Statuses and Tasks to Ayon.")
        create_sg_entities_in_ay(
            self._entity_hub.project_entity,
            self._sg_session,
            self._sg_project,
        )
        prev_step_time = sync_step_time
        sync_step_time = time.perf_counter()
        self.log.debug((
            "Adding Shotgrid Statuses and Tasks to Ayon"
            f"took {sync_step_time - prev_step_time} to load."
        ))

        self.log.info("Querying all Shotgrid Entities.")
        (
            self._sg_entities_by_id,
            self._sg_entities_by_parent_id
        ) = get_sg_entities(
            self._sg_session,
            self._sg_project,
        )

        prev_step_time = sync_step_time
        sync_step_time = time.perf_counter()
        self.log.debug((
            "Querying all Shotgrid Entities and hierrachy took"
            f"{sync_step_time - prev_step_time} to process."
        ))

        self._match_shotgrid_hierarchy()
        self._entity_hub.commit_changes()

        prev_step_time = sync_step_time
        sync_step_time = time.perf_counter()
        self.log.debug((
            "Creating all missing entities in ayon took "
            f"{sync_step_time - prev_step_time} to process."
        ))

    def _match_shotgrid_hierarchy(self):
        project_entity = self._entity_hub.project_entity
        ayon_project_shotgrid_id_attrib = project_entity.attribs.get_attribute(
            SHOTGRID_ID_ATTRIB
        ).value

        if not ayon_project_shotgrid_id_attrib:
            self.log.error((
                "Project creation probably went wrong, there's no shotgridID"
                f"{ayon_project_shotgrid_id_attrib}"
            ))
            return

        if int(self._sg_project["id"]) != int(ayon_project_shotgrid_id_attrib):
            self.log.error((
                "Project creation probably went wrong"
                "IDs for projects do not match."
                f"{self._sg_project['id']} =/= {ayon_project_shotgrid_id_attrib}"
            ))
            return

        sg_entities_deck = collections.deque()

        for sg_project_child in self._sg_entities_by_parent_id[self._sg_project["id"]]:
            sg_entities_deck.append((project_entity, sg_project_child))

        sg_project_sync_status = "Synced"

        while sg_entities_deck:
            (ay_parent_entity, sg_entity) = sg_entities_deck.popleft()
            self.log.debug(f"Processing {sg_entity})")

            ay_entity = None
            sg_entity_sync_status = "Synced"

            for ay_child in ay_parent_entity.children:
                if ay_child.name == sg_entity["name"]:
                    ay_entity = ay_child
                    self.log.debug(f"Entity {ay_entity.name} exists in Ayon.")

            if ay_entity is None:
                ay_entity = self._create_new_entity(
                    ay_parent_entity,
                    sg_entity,
                )

            self.log.debug(f"Updating {ay_entity.name} <{ay_entity.id}>.")
            shotgrid_id_attrib = ay_entity.attribs.get_attribute(
                SHOTGRID_ID_ATTRIB
            ).value

            if not shotgrid_id_attrib:
                ay_entity.attribs.set(
                    SHOTGRID_ID_ATTRIB,
                    sg_entity[SHOTGRID_ID_ATTRIB]
                )
                ay_entity.attribs.set(
                    SHOTGRID_TYPE_ATTRIB,
                    sg_entity["type"]
                )
            elif str(shotgrid_id_attrib) != str(sg_entity[SHOTGRID_ID_ATTRIB]):
                self.log.error("Wrong Shotgrid ID in ayon record.")
                sg_entity_sync_status = "Failed"
                sg_project_sync_status = "Failed"
                # Add it to a list of mismatched ? deal this somehow

            # Update SG entity with new created data
            sg_entity[CUST_FIELD_CODE_ID] = ay_entity.id

            self._ids_mapping.set_server_to_shotgrid(
                ay_entity.id,
                sg_entity[SHOTGRID_ID_ATTRIB]
            )

            self._sg_entities_by_id[sg_entity[SHOTGRID_ID_ATTRIB]] = sg_entity

            entity_id = sg_entity["name"]

            if sg_entity["type"] != "Folder":
                if (
                    sg_entity[CUST_FIELD_CODE_ID] != ay_entity.id
                    or sg_entity[CUST_FIELD_CODE_SYNC] != sg_entity_sync_status
                ):
                    update_data = {
                        CUST_FIELD_CODE_ID: ay_entity.id,
                        CUST_FIELD_CODE_SYNC: sg_entity[CUST_FIELD_CODE_SYNC]
                    }
                    self._sg_session.update(
                        sg_entity["type"],
                        sg_entity[SHOTGRID_ID_ATTRIB],
                        update_data
                    )

                # If the entity has children, add it to the deck
                entity_id = sg_entity[SHOTGRID_ID_ATTRIB]

            # If the entity has children, add it to the deck
            for sg_child in self._sg_entities_by_parent_id.get(
                entity_id, []
            ):
                sg_entities_deck.append((ay_entity, sg_child))

        self._sg_session.update(
            "Project",
            self._sg_project["id"],
            {
                CUST_FIELD_CODE_ID: project_entity.id,
                CUST_FIELD_CODE_SYNC: sg_project_sync_status
            }
        )

    def _create_new_entity(self, parent_entity, sg_entity):
        """Helper method to create entities in the EntityHub.

        Args:
            parent_entity: Ayon parent entity.
            sg_entity (dict): Shotgrid entity to create.
        """
        if sg_entity["type"].lower() == "task":
            new_entity = self._entity_hub.add_new_task(
                sg_entity["label"],
                name=sg_entity["name"],
                label=sg_entity["label"],
                entity_id=sg_entity[CUST_FIELD_CODE_ID],
                parent_id=parent_entity.id
            )
        else:
            new_entity = self._entity_hub.add_new_folder(
                sg_entity["type"],
                name=sg_entity["name"],
                label=sg_entity["label"],
                entity_id=sg_entity[CUST_FIELD_CODE_ID],
                parent_id=parent_entity.id
            )
        self._ids_mapping.set_shotgrid_to_server(sg_entity[SHOTGRID_ID_ATTRIB], new_entity.id)
        self.log.debug(f"Created new entity: {new_entity.name} ({new_entity.id})")
        self.log.debug(f"Parent is: {parent_entity.name} ({parent_entity.id})")
        return new_entity

