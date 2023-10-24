"""
Handle Events originated from Shotgrid.
"""
from shotgrid_common.ayon_shotgrid_hub import AyonShotgridHub

from nxtools import logging

REGISTER_EVENT_TYPE = ["shotgrid-event"]


def process_event(
    sg_url,
    sg_script_name,
    sg_api_key,
    user_name=None,
    project_name=None,
    project_code=None,
    sg_payload=None,
    **kwargs,
):
    """React to Shotgrid Events.

    Events with the action `shotgrid-event` will trigger this
    function, where we attempt to replicate a change coming form Shotgrid, like
    creating a new Shot, renaming a Task, etc.
    """
    if not sg_payload:
        logging.error("The Event payload is empty!")
        raise ValueError("The Event payload is empty!")

    if not sg_payload.get("meta", {}):
        logging.error("The Event payload is missing the action to perform!")
        raise ValueError("The Event payload is missing the action to perform!")

    hub = AyonShotgridHub(
        project_name,
        project_code,
        sg_url,
        sg_api_key,
        sg_script_name,
    )

    hub.react_to_shotgrid_event(sg_payload["meta"])

