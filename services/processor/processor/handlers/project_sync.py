"""
Ensure that the project has all the required things in both Ayon and Shotgrid,
custom attributes, tasks types and statuses.
"""
import re

from processor.lib.sync_from_shotgrid import SyncFromShotgrid
from processor.lib.utils import (
    create_ay_fields_in_sg_project,
    create_ay_fields_in_sg_entities,
    get_sg_project_by_name,
    create_sg_entities_in_ay
)
from processor.lib.constants import (
    SHOTGRID_ID_ATTRIB,
    CUST_FIELD_CODE_ID,
    CUST_FIELD_CODE_CODE,
    CUST_FIELD_CODE_URL
)


from ayon_api import (
    create_project,
    get_base_url,
    get_project,
    get_project_anatomy_preset,
    post
)
from ayon_api.entity_hub import EntityHub
from nxtools import logging, log_traceback


REGISTER_EVENT_TYPE = ["create-project"]
PROJECT_NAME_REGEX = re.compile(
    "^[{}]+$".format("a-zA-Z0-9_")
)


def process_event(
    shotgrid_session,
    user_name=None,
    project_name=None,
    project_code=None,
    **kwargs,
):
    """Entry point of the processor"""
    if not project_name:
        logging.error("Can't create a project without a name!")
        raise ValueError

    if not project_code:
        logging.error("Can't create a project without a code!")
        raise ValueError

    project_code_field = kwargs.get("project_code_field", "code")

    logging.debug("Finding Project in Shotgrid...")
    shotgrid_project = get_sg_project_by_name(
        shotgrid_session,
        project_name
    )

    if not shotgrid_project:
        logging.error(f"Could not find {project_name} in Shotgrid!")
        raise ValueError

    try:
        ayon_project = get_project(project_name)
    except Exception:
        ayon_project = None

    if ayon_project:
        logging.info(f"Project {project_name} already exists in Ayon.")
        logging.info("Try Sync Project in the Settings > Shotgrid Sync tab!")
        return

    try:
        if not ayon_project:
            logging.info(f"Creating project {project_name} in Ayon.")
            ayon_project = create_project(project_name, project_code)
    except Exception as e:
        logging.error("Unable to create the Ayon project.")
        log_traceback(e)
        # We would normally retunr here, but thers a bug currently in `ayon_api`
        # return

    try:
        ayon_project = get_project(project_name)
    except Exception:
        ayon_project = None

    if not ayon_project:
        logging.error("Definetly Unable to create the Ayon project.")
        return

    logging.debug(f"Ayon project is: {ayon_project}")

    entity_hub = EntityHub(project_name)
    logging.debug(f"Ayon Project attrib {SHOTGRID_ID_ATTRIB} > {shotgrid_project['id']}.")
    entity_hub.project_entity.attribs.set(
        SHOTGRID_ID_ATTRIB,
        shotgrid_project["id"]
    )
    entity_hub.commit_changes()
    entity_hub.query_entities_from_server()

    logging.debug("Ensure Ayon has all the Tasks and Folder from Shotgrid.")
    create_sg_entities_in_ay(
        entity_hub.project_entity,
        shotgrid_session,
        shotgrid_project
    )
    entity_hub.commit_changes()

    logging.debug("Creating all required Project fields in Shotgrid.")
    create_ay_fields_in_sg_project(shotgrid_session)
    shotgrid_session.update(
        "Project",
        shotgrid_project["id"],
        {
            CUST_FIELD_CODE_ID: ayon_project["name"],
            project_code_field: ayon_project["code"],
            CUST_FIELD_CODE_URL: get_base_url(),
        }
    )

    logging.debug("Creating Ayon ID and Ayon Sync Status on all entities.")
    create_ay_fields_in_sg_entities(shotgrid_session)

    logging.debug("Trigger the initial Sync.")
    sg_sync = SyncFromShotgrid(shotgrid_session, project_name, project_code_field, log=logging)
    sg_sync.sync_to_ayon()

