"""
Ensure that the project has all the required things in both Ayon and Shotgrid,
custom attributes, tasks types and statuses.
"""
from processor.lib.sync_from_ayon import SyncFromAyon
from processor.lib.utils import (
    get_sg_project_by_name,
)
from processor.lib.constants import CUST_FIELD_CODE_SYNC


from ayon_api import get_project
from ayon_api.entity_hub import EntityHub
from nxtools import logging, log_traceback


REGISTER_EVENT_TYPE = ["sync-from-shotgrid"]


def process_event(
    shotgrid_session,
    user_name=None,
    project_name=None,
    **kwargs,
):
    """Entry point of the processor"""
    if not project_name:
        logging.error("Can't Sync a project without a name!")
        return

    try:
        shotgrid_project = get_sg_project_by_name(
            shotgrid_session,
            project_name
        )
    except ValueError:
        logging.error(f"Could not find {project_name} in Shotgrid!")
        return

    try:
        ayon_project = get_project(project_name)
    except Exception as e:
        logging.error(f"Project {project_name} does not exists in Ayon.")
        logging.error("Run Create Project from the Settings > Shotgrid Sync.")
        log_traceback(e)
        return

    logging.debug(f"Ayon project is: {ayon_project}")

    try:
        # Trigger a one time Sync.
        sg_sync = SyncFromAyon(shotgrid_session, project_name, log=logging)
        sg_sync.sync_to_shotgrid()
    except Exception as e:
        logging.error(f"Shotgrid Sync of project {project_name} failed!")
        log_traceback(e)
        shotgrid_session.update(
            "Project",
            shotgrid_project["id"],
            {CUST_FIELD_CODE_SYNC: "Failed"}
        )
        return

