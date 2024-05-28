"""
Handle Events originated from Shotgrid.
"""
from ayon_shotgrid_hub import AyonShotgridHub


REGISTER_EVENT_TYPE = ["shotgrid-event"]


def process_event(
    sg_processor,
    **kwargs,
):
    """React to Shotgrid Events.

    Events with the action `shotgrid-event` will trigger this
    function, where we attempt to replicate a change coming form Shotgrid, like
    creating a new Shot, renaming a Task, etc.
    """
    sg_payload = kwargs.get("sg_payload", {})
    if not sg_payload:
        raise ValueError("The Event payload is empty!")

    if not sg_payload.get("meta", {}):
        raise ValueError("The Event payload is missing the action to perform!")

    hub = AyonShotgridHub(
        kwargs.get("project_name"),
        kwargs.get("project_code"),
        sg_processor.sg_url,
        sg_processor.sg_api_key,
        sg_processor.sg_script_name,
        sg_project_code_field=sg_processor.sg_project_code_field,
        custom_attribs_map=sg_processor.custom_attribs_map,
        custom_attribs_types=sg_processor.custom_attribs_types,
        sg_enabled_entities=sg_processor.sg_enabled_entities,
    )

    hub.react_to_shotgrid_event(sg_payload["meta"])
