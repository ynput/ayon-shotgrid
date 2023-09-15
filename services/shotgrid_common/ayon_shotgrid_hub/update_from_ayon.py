"""Class that will create, update or remove an Shotgrid entity based on an AYON event.
"""

from ..utils import (
    get_sg_entity_as_ay_dict,
    get_sg_entity_parent_field,
    get_sg_project_by_id
)
from ..constants import (
    CUST_FIELD_CODE_ID,  # Shotgrid Field for the Ayon ID.
    SHOTGRID_ID_ATTRIB,  # Ayon Entity Attribute.
    SHOTGRID_TYPE_ATTRIB,  # Ayon Entity Attribute.
    SHOTGRID_REMOVED_VALUE
)

from ayon_api import get_project
from ayon_api.entity_hub import EntityHub
from nxtools import logging, log_traceback

def create_sg_entity_from_ayon_event(ayon_event, sg_session, ayon_entity_hub):
    """Create an AYON entity from a Shotgrid Event.

    Args:
        sg_event (dict): The `meta` key from a Shotgrid Event.
        sg_project (dict): The Shotgrid project.
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.

    Returns:
        ay_entity (ayon_api.entity_hub.EntityHub.Entity): The newly created entity.
    """
    ay_entity = ayon_entity_hub.query_entities_from_server(
        ayon_event["summary"]["entityId"]
    )

    if not ay_entity:
        logging.error(
            f"Event has a non existant entity? {ayon_event['summary']['entityId']}"
        )
        return

    sg_id = ay_entity.attribs.get("shotgridId")
    sg_type = ay_entity.attribs.get("shotgridType")

    sg_entity = sg_session.find_one(sg_type, [["id", "is", int(sg_id)]])
    if sg_entity:
        logging.warning(f"Entity {sg_entity} already exists in Shotgrid!")

    sg_project_id = ayon_entity_hub.project_entity.attribs.get("shotgridId")

    if not sg_project_id:
        logging.error("Project has not Shotgrid ID specified, please use the Shotgrid Sync to repair it.")
        return

    sg_project = get_sg_project_by_id(sg_project_id)

    try:
        sg_entity = _create_sg_entity(
            sg_session,
            ay_entity,
            sg_project,
            sg_type,
        )
        logging.info(f"Created Shotgrid entity: {sg_entity}")

        ay_entity.attribs.set(
            SHOTGRID_ID_ATTRIB,
            sg_entity["id"]
        )
        ay_entity.attribs.set(
            SHOTGRID_TYPE_ATTRIB,
            sg_entity["type"]
        )
        ayon_entity_hub.commit_changes()
    except Exception as e:
        logging.error(f"Unable to create {sg_type} <{ayon_event['summary']['entityId']}> in Shotgrid!")
        log_traceback(e)


def update_sg_entity_from_ayon_event(ayon_event, sg_session, ayon_entity_hub):
    """Try to update an entity in Ayon.

    Args:
        sg_event (dict): The `meta` key from a Shotgrid Event.
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.

    Returns:
        ay_entity (ayon_api.entity_hub.EntityHub.Entity): The modified entity.

    """
    ay_entity = ayon_entity_hub.query_entities_from_server(ayon_event["summary"]["entityId"])
    sg_id = ay_entity.attribs.get("shotgridId")
    sg_type = ay_entity.attribs.get("shotgridType")

    try:
        sg_field_name = "code"

        if ay_entity.get("taskType"):
            sg_field_name = "content"

        sg_entity = sg_session.update(
            sg_type,
            sg_id,
            {
                sg_field_name: ay_entity["name"],
                CUST_FIELD_CODE_ID: ay_entity["id"]
            }
        )
        logging.info(f"Updated Shotgrid entity: {sg_entity}")
    except Exception as e:
        logging.error(f"Unable to delete {sg_type} <{sg_id}> in Shotgrid!")
        log_traceback(e)


def remove_sg_entity_from_ayon_event(ayon_event, sg_session, ayon_entity_hub):
    """Try to remove an entity in Ayon.

    Args:
        sg_event (dict): The `meta` key from a Shotgrid Event.
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
    """
    ay_entity = ayon_entity_hub.query_entities_from_server(ayon_event["summary"]["entityId"])
    sg_id = ay_entity.attribs.get("shotgridId")
    sg_type = ay_entity.attribs.get("shotgridType")

    try:
        sg_session.delete(sg_type, sg_id)
        logging.info(f"Retired Shotgrid entity: {sg_type} <{sg_id}>")
    except Exception as e:
        logging.error(f"Unable to delete {sg_type} <{sg_id}> in Shotgrid!")
        log_traceback(e)


def _create_sg_entity(
    sg_session,
    ay_entity,
    sg_project,
    sg_type,
):
    """ Create a new Shotgrid entity.

    Args:
        ay_entity (dict): The AYON entity.
        sg_project (dict): The Shotgrid Project.
        sg_type (str): The Shotgrid type of the new entity.
    """
    sg_field_name = "code"

    if ay_entity.entity_type == "task":
        sg_field_name = "content"

    sg_parent_id = ay_entity.parent.attribs.get(SHOTGRID_ID_ATTRIB)
    sg_parent_type = ay_entity.parent.attribs.get(SHOTGRID_TYPE_ATTRIB)

    if not (sg_parent_id and sg_parent_type):
        logging.error("Parent does not exist in Shotgird!")
        #create parent ?
        return

    parent_field = get_sg_entity_parent_field(
        sg_session,
        sg_project,
        sg_parent_type,
    )

    data = {
        "project": sg_project,
        parent_field: {"type": sg_parent_type, "id": int(sg_parent_id)},
        sg_field_name: ay_entity.name,
        CUST_FIELD_CODE_ID: ay_entity.id,
    }

    return sg_session.create(sg_type, data)


