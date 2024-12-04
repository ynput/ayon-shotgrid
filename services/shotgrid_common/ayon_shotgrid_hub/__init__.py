""" Influenced by the `ayon_api.EntityHub` the `AyonShotgridHub` is a class
that provided a valid Project name and code, will perform all the necessary
checks and provide methods to keep an AYON and Shotgrid project in sync.
"""
import re

from constants import (
    AYON_SHOTGRID_ENTITY_TYPE_MAP,
    CUST_FIELD_CODE_AUTO_SYNC,
    CUST_FIELD_CODE_CODE,
    CUST_FIELD_CODE_ID,
    CUST_FIELD_CODE_URL,
    SHOTGRID_ID_ATTRIB,
    SHOTGRID_TYPE_ATTRIB
)

from .match_shotgrid_hierarchy_in_ayon import match_shotgrid_hierarchy_in_ayon
from .match_ayon_hierarchy_in_shotgrid import match_ayon_hierarchy_in_shotgrid

from .update_from_shotgrid import (
    create_ay_entity_from_sg_event,
    update_ayon_entity_from_sg_event,
    remove_ayon_entity_from_sg_event
)
from .update_from_ayon import (
    create_sg_entity_from_ayon_event,
    update_sg_entity_from_ayon_event,
    remove_sg_entity_from_ayon_event
)

from utils import (
    create_ay_fields_in_sg_project,
    create_ay_fields_in_sg_entities,
    create_sg_entities_in_ay,
    get_sg_project_enabled_entities,
    get_sg_project_by_name,
)

import ayon_api
from ayon_api.entity_hub import EntityHub

from utils import get_logger


PROJECT_NAME_REGEX = re.compile("^[a-zA-Z0-9_]+$")


class AyonShotgridHub:
    """A Hub to manage a Project in both AYON and Shotgrid

    Provided a correct project name and code, we attempt to initialize both APIs
    and ensures that both platforms have the required elements to synchronize a
    project across them.

    The Shotgrid credentials must have enough permissions to add fields to
    entities and create entities/projects.

    Args:
        sg_connection (shotgun_api3.Shotgun): The Shotgrid connection.
        project_name (str):The project name, cannot contain spaces.
        project_code (str): The project code (3 letter code).
        sg_project_code_field (str): The field in the Shotgrid Project entity
            that represents the project code.
        custom_attribs_map (dict): A dictionary mapping AYON attributes to
            Shotgrid fields, without the `sg_` prefix.
        custom_attribs_types (dict): A dictionary mapping AYON attribute types
            to Shotgrid field types.
    """

    log = get_logger(__file__)
    custom_attribs_map = {
        "status": "status_list",
        "tags": "tags"
    }

    def __init__(self,
        sg_connection,
        project_name,
        project_code,
        sg_project_code_field=None,
        custom_attribs_map=None,
        custom_attribs_types=None,
        sg_enabled_entities=None,
    ):
        self.settings = ayon_api.get_service_addon_settings(project_name)

        self._sg = sg_connection

        self._ay_project = None
        self._sg_project = None

        if sg_project_code_field:
            self.sg_project_code_field = sg_project_code_field
        else:
            self.sg_project_code_field = "code"

        # add custom attributes from settings
        if custom_attribs_map:
            self.custom_attribs_map.update(custom_attribs_map)

        self.custom_attribs_types = custom_attribs_types

        if sg_enabled_entities:
            self.sg_enabled_entities = sg_enabled_entities
        else:
            self.sg_enabled_entities = list(AYON_SHOTGRID_ENTITY_TYPE_MAP)

        self.project_name = project_name
        self.project_code = project_code

    def create_sg_attributes(self):
        """Create all AYON needed attributes in Shotgrid."""
        create_ay_fields_in_sg_project(
            self._sg, self.custom_attribs_map, self.custom_attribs_types
        )
        create_ay_fields_in_sg_entities(
            self._sg,
            self.sg_enabled_entities,
            self.custom_attribs_map,
            self.custom_attribs_types
        )

    @property
    def project_name(self):
        return self._project_name

    @project_name.setter
    def project_name(self, project_name):
        """Set the project name

        We make sure the name follows the conventions imposed by ayon-backend,
        and if it passes we attempt to find the project in both platfomrs.
        """
        if not PROJECT_NAME_REGEX.match(project_name):
            raise ValueError(f"Invalid Project Name: {project_name}")

        self._project_name = project_name

        try:
            self._ay_project = EntityHub(project_name)
            self._ay_project.project_entity
        except Exception:
            self.log.warning(f"Project {project_name} does not exist in AYON.")
            self._ay_project = None

        custom_fields = [
            self.sg_project_code_field,
            CUST_FIELD_CODE_AUTO_SYNC,
        ]
        for attrib in self.custom_attribs_map.values():
            custom_fields.extend([f"sg_{attrib}", attrib])

        try:
            self._sg_project = get_sg_project_by_name(
                self._sg,
                self.project_name,
                custom_fields=custom_fields
            )
        except Exception:
            self.log.warning(f"Project {project_name} does not exist in Shotgrid. ")
            self._sg_project = None

    def create_project(self):
        """Create project in AYON and Shotgrid.
        """
        if self._ay_project is None:
            anatomy_preset_name = self.settings.get("anatomy_preset", None)

            # making sure build in preset is not used
            if anatomy_preset_name == "_":
                anatomy_preset_name = None

            self.log.info(
                f"Creating AYON project {self.project_name}\n"
                f"- project code: {self.project_code}\n"
                f"- anatomy preset: {anatomy_preset_name}\n"
            )
            ayon_api.create_project(
                self.project_name,
                self.project_code,
                preset_name=anatomy_preset_name
            )
            self._ay_project = EntityHub(self.project_name)
            self._ay_project.query_entities_from_server()

        self._ay_project.commit_changes()

        if self._sg_project is None:
            self.log.info(f"Creating Shotgrid project {self.project_name} (self.project_code).")
            self._sg_project = self._sg.create(
                "Project",
                {
                    "name": self.project_name,
                    self.sg_project_code_field: self.project_code,
                    CUST_FIELD_CODE_ID: self.project_name,
                    CUST_FIELD_CODE_CODE: self.project_code,
                    CUST_FIELD_CODE_URL: ayon_api.get_base_url(),
                }
            )
            self._ay_project.project_entity.attribs.set(
                SHOTGRID_ID_ATTRIB,
                self._sg_project["id"]
            )

            self._ay_project.project_entity.attribs.set(
                SHOTGRID_TYPE_ATTRIB,
                "Project"
            )
            self._ay_project.commit_changes()

        self.create_sg_attributes()
        self.log.info(f"Project {self.project_name} ({self.project_code}) available in SG and AYON.")

    def synchronize_projects(self, source="ayon"):
        """ Ensure a Project matches in the other platform.

        Args:
            source (str): Either "ayon" or "shotgrid", dictates which one is the
                "source of truth".
        """
        if not self._ay_project or not self._sg_project:
            raise ValueError("""The project is missing in one of the two platforms:
                AYON: {0}
                Shotgrid: {1}""".format(self._ay_project, self._sg_project)
            )

        match source:
            case "ayon":
                disabled_entities = []
                ay_entities = [
                    folder["name"]
                    for folder in self._ay_project.project_entity.folder_types
                    if folder["name"] in self.sg_enabled_entities
                ]

                sg_entities = [
                    entity_name
                    for entity_name, _ in get_sg_project_enabled_entities(
                        self._sg,
                        self._sg_project,
                        self.sg_enabled_entities
                    )
                ]

                disabled_entities = [
                    ay_entity
                    for ay_entity in ay_entities
                    if ay_entity not in sg_entities
                ]

                if disabled_entities:
                    raise ValueError(
                        f"Unable to sync project {self.project_name} "
                        f"<{self.project_code}> from AYON to Shotgrid, you need "
                        "to enable the following entities in the Shotgrid Project "
                        f"> Project Actions > Tracking Settings: {disabled_entities}"
                    )

                match_ayon_hierarchy_in_shotgrid(
                    self._ay_project,
                    self._sg_project,
                    self._sg,
                    self.sg_enabled_entities,
                    self.sg_project_code_field,
                    self.custom_attribs_map,
                    self.settings,
                )

            case "shotgrid":
                create_sg_entities_in_ay(
                    self._ay_project.project_entity,
                    self._sg,
                    self._sg_project,
                    self.sg_enabled_entities,
                )
                self._ay_project.commit_changes()

                match_shotgrid_hierarchy_in_ayon(
                    self._ay_project,
                    self._sg_project,
                    self._sg,
                    self.sg_enabled_entities,
                    self.sg_project_code_field,
                    self.custom_attribs_map,
                    self.settings
                )

            case _:
                raise ValueError(
                    "The `source` argument can only be `ayon` or `shotgrid`."
                )

    def react_to_shotgrid_event(self, sg_event_meta):
        """React to events incoming from Shotgrid

        Whenever there's a `shotgrid.event` spawned by the `leecher` of a change
        in Shotgrid, we pass said event.

        The current scope of what changes and what attributes we care is limited,
        this is to be expanded.

        Args:
            sg_event_meta (dict): The `meta` key of a ShotGrid Event, describing
                what the change encompasses, i.e. a new shot, new asset, etc.
        """
        if not self._ay_project:
            self.log.info(
                f"Ignoring event, AYON project {self.project_name} not found.")
            return

        # revival of Asset with tasks will send first retirement_date changes
        # on tasks, then retirement_date change on Asset AND only then revival
        # of Asset
        if (
            sg_event_meta["type"] == "attribute_change"
            and sg_event_meta["attribute_name"] == "retirement_date"
            and sg_event_meta["new_value"] is None  # eg revival
        ):
            if sg_event_meta["entity_type"].lower() == "asset":
                # do not do updates on not yet existing asset
                return

            self.log.info("Changed 'retirement_date' event to "
                          f"'entity_revival' for Task | "
                          f"{sg_event_meta['entity_id']}.")
            sg_event_meta["type"] = "entity_revival"

        match sg_event_meta["type"]:
            case "new_entity" | "entity_revival":
                self.log.info(
                    f"Creating entity from SG event: {sg_event_meta['type']}"
                    f"| {sg_event_meta['entity_type']} "
                    f"| {sg_event_meta['entity_id']}"
                )
                create_ay_entity_from_sg_event(
                    sg_event_meta,
                    self._sg_project,
                    self._sg,
                    self._ay_project,
                    self.sg_enabled_entities,
                    self.sg_project_code_field,
                    self.custom_attribs_map,
                    self.settings
                )

            case "attribute_change":
                self.log.info(
                    f"Updating entity from SG event: {sg_event_meta['type']} "
                    f"| {sg_event_meta['entity_type']} "
                    f"| {sg_event_meta['entity_id']}"
                )
                update_ayon_entity_from_sg_event(
                    sg_event_meta,
                    self._sg_project,
                    self._sg,
                    self._ay_project,
                    self.sg_enabled_entities,
                    self.sg_project_code_field,
                    self.settings,
                    self.custom_attribs_map,
                )

            case "entity_retirement":
                self.log.info(
                    f"Removing entity from SG event: {sg_event_meta['type']}"
                    f"| {sg_event_meta['entity_type']} "
                    f"| {sg_event_meta['entity_id']}"
                )
                remove_ayon_entity_from_sg_event(
                    sg_event_meta,
                    self._sg,
                    self._ay_project,
                    self.sg_project_code_field,
                    self.settings,
                )

            case _:
                raise ValueError(
                    f"Unable to process event {sg_event_meta['type']}.")

    def react_to_ayon_event(self, ayon_event):
        """React to events incoming from AYON

        Whenever there's a `entity.<entity-type>.<action>` in AYON, where we create,
        update or delete an entity, we attempt to replicate the action in Shotgrid.

        The current scope of what changes and what attributes we care is limited,
        this is to be expanded.

        Args:
            ayon_event (dict): A dictionary describing what
                the change encompases, i.e. a new shot, new asset, etc.
        """
        if not self._sg_project[CUST_FIELD_CODE_AUTO_SYNC]:
            self.log.info(
                "Ignoring event, Shotgrid field 'Ayon Auto Sync' is disabled."
            )
            return

        match ayon_event["topic"]:
            case "entity.task.created" | "entity.folder.created":
                create_sg_entity_from_ayon_event(
                    ayon_event,
                    self._sg,
                    self._ay_project,
                    self._sg_project,
                    self.sg_enabled_entities,
                    self.custom_attribs_map,
                )

            case "entity.task.deleted" | "entity.folder.deleted":
                remove_sg_entity_from_ayon_event(
                    ayon_event,
                    self._sg,
                )

            case "entity.task.renamed" | "entity.folder.renamed":
                update_sg_entity_from_ayon_event(
                    ayon_event,
                    self._sg,
                    self._ay_project,
                )
            case "entity.task.attrib_changed" | "entity.folder.attrib_changed":
                attrib_key = next(iter(ayon_event["payload"]["newValue"]))
                if attrib_key not in self.custom_attribs_map:
                    self.log.warning(
                        f"Updating attribute '{attrib_key}' from AYON to SG "
                        f"not supported: {self.custom_attribs_map}."
                    )
                    return
                update_sg_entity_from_ayon_event(
                    ayon_event,
                    self._sg,
                    self._ay_project,
                    self.custom_attribs_map,
                )
            case "entity.task.status_changed" | "entity.folder.status_changed" | "entity.task.tags_changed" | "entity.folder.tags_changed":
                # TODO: for some reason the payload here is not a dict but we know
                # we always want to update the entity
                update_sg_entity_from_ayon_event(
                    ayon_event,
                    self._sg,
                    self._ay_project,
                    self.custom_attribs_map,
                )
            case _:
                raise ValueError(
                    f"Unable to process event {ayon_event['topic']}."
                )
