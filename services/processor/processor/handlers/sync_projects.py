"""Sync Projects - A `processor.handler` to ensure two Projects
are in sync between AYON and Shotgrid, uses the `AyonShotgridHub`.
"""
from processor.ayon_shotgrid_hub import AyonShotgridHub


from nxtools import logging, log_traceback


REGISTER_EVENT_TYPE = ["sync-from-shotgrid", "sync-from-ayon"]


def process_event(
    sg_url,
    sg_script_name,
    sg_api_key,
    user_name=None,
    project_name=None,
    project_code=None,
    **kwargs,
):
    """Syncronize a project between AYON and Shotgrid.

    Events with the action `sync-from-shotgrid` or `sync-from-ayon` will trigger
    this function, where we travees a whole project, either in Shotgrid or AYON,
    and replciate it's structe in the other platform.
    """
    hub = AyonShotgridHub(
        project_name,
        project_code,
        sg_url,
        sg_api_key,
        sg_script_name,
    )

    hub.create_project()
    hub.syncronize_projects(
        source="ayon" if kwargs.get("action") == "sync-from-ayon" else "shotgrid"
    )

