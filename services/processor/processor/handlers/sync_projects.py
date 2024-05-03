"""Sync Projects - A `processor.handler` to ensure two Projects
are in sync between AYON and Shotgrid, uses the `AyonShotgridHub`.
"""
from ayon_shotgrid_hub import AyonShotgridHub


REGISTER_EVENT_TYPE = ["sync-from-shotgrid", "sync-from-ayon"]


def process_event(
    sg_processor,
    **kwargs,
):
    """Synchronize a project between AYON and Shotgrid.

    Events with the action `sync-from-shotgrid` or `sync-from-ayon` will trigger
    this function, where we travees a whole project, either in Shotgrid or AYON,
    and replciate it's structe in the other platform.
    """
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

    # This will ensure that the project exists in both platforms.
    hub.create_project()
    hub.synchronize_projects(
        source="ayon" if kwargs.get("action") == "sync-from-ayon" else "shotgrid"
    )
