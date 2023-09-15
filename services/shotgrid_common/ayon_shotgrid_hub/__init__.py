""" Influenced by the `ayon_api.EntityHub` the `AyonShotgridHub` is a class
that provided a valid Project name and code, will perform all the necessary
checks and provide methods to keep an Ayon and Shotgrid project in sync.
"""
import re

from constants import (
    CUST_FIELD_CODE_ID,
    CUST_FIELD_CODE_CODE,
    CUST_FIELD_CODE_URL
)

from .match_shotgrid_hierarchy_in_ayon import match_shotgrid_hierarchy_in_ayon
from .update_from_shotgrid import (
    create_ay_entity_from_sg_event,
    update_ayon_entity_from_sg_event,
    remove_ayon_entity_from_sg_event
)

from utils import (
    create_ay_fields_in_sg_project,
    create_ay_fields_in_sg_entities,
    create_sg_entities_in_ay,
    get_sg_project_by_name,
    get_sg_missing_ay_attributes,
)

import ayon_api
from ayon_api.entity_hub import EntityHub
from nxtools import logging, log_traceback
import shotgun_api3

PROJECT_NAME_REGEX = re.compile("^[a-zA-Z0-9_]+$")


class AyonShotgridHub:
    """A Hub to manage a Project in both AYON and Shotgrid

    Provided a correct project name and code, we attempt to initialize both APIs
    and ensures that both platforms have the required elements to syncronize a
    project across them.

    The Shotgrid credentials must have enough permissions to add fields to
    entities and create entities/projects.

    Args:
        project_name (str):The project name, cannot contain spaces.
        project_code (str): The project code (3 letter code).
        sg_url (str): The URL of the Shotgrid instance.
        sg_api_key (str): The API key of the Shotgrid instance.
        sg_script_name (str): The Script Name of the Shotgrid instance.
    """
    def __init__(self,
        project_name,
        project_code,
        sg_url,
        sg_api_key,
        sg_script_name,
    ):

        self._sg = None

        if not all([sg_url, sg_api_key, sg_script_name]):
            msg = (
                "AyonShotgridHub requires `sg_url`, `sg_api_key`" \
                "and `sg_script_name` as arguments."
            )
            logging.error(msg)
            raise ValueError(msg)

        self._initialize_apis(sg_url, sg_api_key, sg_script_name)

        self._ay_project = None
        self._sg_project = None

        self.project_name = project_name
        self.project_code = project_code


    def _initialize_apis(self, sg_url=None, sg_api_key=None, sg_script_name=None):
        """ Ensure we can talk to AYON and Shotgrid.

        Start connections to the APIs and catch any possible error, we abort if
        this steps fails for any reason.
        """
        try:
            ayon_api.init_service()
        except Exception as e:
            logging.error("Unable to connect to AYON.")
            log_traceback(e)
            raise(e)

        if self._sg is None:
            try:
                self._sg = shotgun_api3.Shotgun(
                    sg_url,
                    script_name=sg_script_name,
                    api_key=sg_api_key
                )
            except Exception as e:
                logging.error("Unable to create Shotgrid Session.")
                log_traceback(e)
                raise(e)

        try:
            self._sg.connect()
            logging.debug("Succesfully connected to Shotgrid.")

            try:
                self._check_for_missing_sg_attributes()
            except ValueError as e:
                logging.warning(e)

        except Exception as e:
            logging.error("Unable to connect to Shotgrid.")
            log_traceback(e)
            raise(e)

    def _check_for_missing_sg_attributes(self):
        """Check if Shotgrid has all the fields.

        In order to sync to work, Shotgrid needs to have certain fields in both
        the Project and the entities within it, if any is missing this will raise.
        """
        missing_attributes = get_sg_missing_ay_attributes(self._sg)

        if missing_attributes:
            raise ValueError("""Shotgrid Project is missing the following attributes: {0}
            Use `AyonShotgridHub.create_sg_attributes()` to create them.""".format(
                "\n".join(missing_attributes)
            ))

    def create_sg_attributes(self):
        """Create all AYON needed attributes in Shotgrid."""
        create_ay_fields_in_sg_project(self._sg)
        create_ay_fields_in_sg_entities(self._sg)

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
            logging.warning(f"Project {project_name} does not exist in AYON.")
            self._ay_project = None

        try:
            self._sg_project = get_sg_project_by_name(
                self._sg,
                self.project_name
            )
        except Exception:
            logging.warning(f"Project {project_name} does not exist in Shotgrid.")
            self._sg_project = None

    def create_project(self):
        """Create project in AYON and Shotgrid.

        This step is also where we create all the required fields in Shotgrid
        entities.
        """
        if self._ay_project is None:
            logging.info(f"Creating AYON project {self.project_name} ({self.project_code}).")
            ayon_api.create_project(self.project_name, self.project_code)
            self._ay_project = EntityHub(self.project_name)
            self._ay_project.query_entities_from_server()
        else:
            logging.info(f"Project {self.project_name} ({self.project_code}) already exists in AYON.")

        self.create_sg_attributes()

        if self._sg_project is None:
            logging.info(f"Creating Shotgrid project {self.project_name} (self.project_code).")
            self._sg_project = self._sg.create(
                "Project",
                {
                    "name": self.project_name,
                    CUST_FIELD_CODE_ID: self.project_name,
                    CUST_FIELD_CODE_CODE: self.project_code,
                    CUST_FIELD_CODE_URL: ayon_api.get_base_url(),
                }
            )
        else:
            logging.info(f"Project {self.project_name} ({self.project_code}) already exists in SG.")

    def syncronize_projects(self, source="ayon"):
        """ Ensure a Project matches in the other platform.

        Args:
            source (str): Either "ayon" or "shotgrid", dictates which one is the
                "source of truth".
        """
        if not self._ay_project or not self._sg_project:
            raise ValueError("""The project is missing in one of the two platforms:
                AYON: {0}
                Shotgrid:{1}""".format(self._ay_project, self._sg_project)
            )

        match source:
            case "shotgrid":
                create_sg_entities_in_ay(
                    self._ay_project.project_entity,
                    self._sg,
                    self._sg_project,
                )
                match_shotgrid_hierarchy_in_ayon(
                    self._ay_project,
                    self._sg_project,
                    self._sg
                )

            case _:
                raise ValueError(
                    "The `source` argument can only be `ayon` or `shotgrid`."
                )

    def react_to_shotgrid_event(self, sg_event):
        """React to events incoming from Shotgrid

        Whenever there's a `shotgrid.event` spawned by the `leecher` of a change
        in Shotgrid, we pass said event.

        The current scope of what changes and what attributes we care is limited,
        this is to be expanded.

        Args:
            sg_event (dict): The `meta` key of a Shogrid Event, describing what
                the change encompases, i.e. a new shot, new asset, etc.
        """
        match sg_event["type"]:
            case "new_entity" | "entity_revival":
                create_ay_entity_from_sg_event(
                    sg_event,
                    self._sg_project,
                    self._sg,
                    self._ay_project
                )

            case "attribute_change":
                if sg_event["attribute_name"] not in ("code", "name"):
                    logging.warning("Can't handle this attribute.")
                    return
                update_ayon_entity_from_sg_event(
                    sg_event,
                    self._sg,
                    self._ay_project
                )

            case "entity_retirement":
                remove_ayon_entity_from_sg_event(
                    sg_event,
                    self._sg,
                    self._ay_project
                )

            case _:
                msg = f"Unable to process event {sg_event['type']}."
                logging.error(msg)
                raise ValueError(msg)

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
        ay_id = ayon_event["summary"]["entityId"]
        ay_entity = self._ay_project.query_entities_from_server(ay_id)

        if not ay_entity:
            logging.error(f"Event has a non existant entity? {ay_id}")
            return

        match ayon_event["topic"]:
            case "entity.task.created" | "entity.folder.created":
                create_sg_entity_from_ayon_event()

            case "entity.task.deleted" | "entity.folder.deleted":
                remove_sg_entity_from_ayon_event()

            case "entity.task.renamed" | "entity.folder.renamed":
                update_sg_entity_from_ayon_event()

            case _:
                msg = f"Unable to process event {ayon_event['topic']}."
                logging.error(msg)
                raise ValueError(msg)

