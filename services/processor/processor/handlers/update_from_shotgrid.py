"""
Handle Events originated from Shotgrid.
"""
from nxtools import logging

from processor.lib.update_from_shotgrid import UpdateFromShotgrid
from processor.lib.constants import CUST_FIELD_CODE_ID, CUST_FIELD_CODE_AUTO_SYNC
from processor.lib.utils import get_sg_project_by_id

REGISTER_EVENT_TYPE = ["shotgrid-event"]
FIELDS_WE_CARE = [
    "code",
    "name",
    CUST_FIELD_CODE_ID,
]


def process_event(
    shotgrid_session,
    sg_payload=None,
    **kwargs
):
    """Entry point of the processor"""
    if not sg_payload:
        logging.error("The Event payload is empty!")
        raise ValueError("The Event payload is empty!")

    if not sg_payload.get("meta", {}):
        logging.error("The Event payload is missing the action to perform!")
        raise ValueError("The Event payload is missing the action to perform!")

    sg_project = get_sg_project_by_id(
        shotgrid_session,
        sg_payload["project"]["id"],
        extra_fields=[CUST_FIELD_CODE_AUTO_SYNC]
    )

    if not sg_project.get(CUST_FIELD_CODE_AUTO_SYNC):
        raise ValueError(
            f"Project {sg_project['name']} has AutoSync disabled."
        )

    sg_update = UpdateFromShotgrid(
        shotgrid_session,
        sg_payload
    )

    sg_update.process_event()

