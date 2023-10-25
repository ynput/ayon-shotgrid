"""Class that will create, update or remove an Shotgrid entity based on an AYON event.
"""

from utils import (
    get_sg_entity_as_ay_dict,
    get_sg_entity_parent_field,
    get_sg_project_by_id
)
from constants import (
    CUST_FIELD_CODE_ID,  # Shotgrid Field for the Ayon ID.
    SHOTGRID_ID_ATTRIB,  # Ayon Entity Attribute.
    SHOTGRID_TYPE_ATTRIB,  # Ayon Entity Attribute.
    SHOTGRID_REMOVED_VALUE
)

from ayon_api import get_project
from ayon_api.entity_hub import EntityHub
from nxtools import logging, log_traceback


def create_sg_entity_from_ayon_event(
    ayon_event,
    sg_session,
    ayon_entity_hub,
    sg_project
):
    """Create a Shotgird entity from an AYON event.

    Args:
        sg_event (dict): AYON event.
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        sg_project (dict): The Shotgrid project.

    Returns:
        ay_entity (ayon_api.entity_hub.EntityHub.Entity): The newly created entity.
    """
    logging.debug(f"Processing event {ayon_event}")

    ay_id = ayon_event["summary"]["entityId"]
    ay_entity = ayon_entity_hub.get_or_query_entity_by_id(ay_id, ["folder", "task"])

    if not ay_entity:
        raise ValueError(
            f"Event has a non existant entity? {ayon_event['summary']['entityId']}"
        )

    sg_id = ay_entity.attribs.get("shotgridId")
    sg_type = ay_entity.attribs.get("shotgridType")

    if not sg_type:
        if ay_entity.entity_type == "task":
            sg_type = "Task"
        else:
            sg_type = ay_entity.folder_type

    sg_entity = None

    logging.debug(f"Creating {ay_entity.name} ({sg_type} <{ay_id}>) in Shotgrid.")

    if sg_id and sg_type:
        logging.debug(f"Querying Shotgrid for {sg_type} <{sg_id}>")
        sg_entity = sg_session.find_one(sg_type, [["id", "is", int(sg_id)]])

    if sg_entity:
        logging.warning(f"Entity {sg_entity} already exists in Shotgrid!")

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
        logging.error(f"Unable to create {sg_type} <{ay_id}> in Shotgrid!")
        log_traceback(e)


def update_sg_entity_from_ayon_event(ayon_event, sg_session, ayon_entity_hub):
    """Try to update a Shotgird entity from an AYON event.

    Args:
        sg_event (dict): The `meta` key from a Shotgrid Event.
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.

    Returns:
        sg_entity (dict): The modified Shotgrid entity.

    """
    logging.debug(f"Processing event {ayon_event}")
    ay_id = ayon_event["summary"]["entityId"]
    ay_entity = ayon_entity_hub.get_or_query_entity_by_id(ay_id, ["folder", "task"])

    if not ay_entity:
        raise ValueError(
            f"Event has a non existant entity? {ayon_event['summary']['entityId']}"
        )

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
        return sg_entity
    except Exception as e:
        logging.error(f"Unable to delete {sg_type} <{sg_id}> in Shotgrid!")
        log_traceback(e)


def remove_sg_entity_from_ayon_event(ayon_event, sg_session, ayon_entity_hub):
    """Try to remove a Shotgird entity from an AYON event.

    Args:
        ayon_event (dict): The `meta` key from a Shotgrid Event.
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
    """
    logging.debug(f"Processing event {ayon_event}")
    ay_id = ayon_event["payload"]["entityData"]["id"]
    sg_id = ayon_event["payload"]["entityData"]["attrib"]["shotgridId"]
    sg_type = ayon_event["payload"]["entityData"]["attrib"]["shotgridType"]

    if not sg_type:
        sg_type = ayon_event["payload"]["folderType"]

    if sg_id and sg_type:
        sg_entity = sg_session.find_one(
            sg_type,
            filters=[["id", "is", int(sg_id)]]
        )
    else:
        sg_entity = sg_session.find_one(
            sg_type,
            filters=[[CUST_FIELD_CODE_ID, "is", ay_id]]
        )

    if not sg_entity:
        logging.warning("Unable to find entity {ay_id} in Shotgrid.")
        return

    sg_id = sg_entity["id"]

    try:
        sg_session.delete(sg_type, int(sg_id))
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
    sg_step = None

    if ay_entity.entity_type == "task":
        sg_field_name = "content"
        sg_step = sg_session.find_one(
            "Step",
            filters=[["code", "is", ay_entity.name]],
        )

        if not sg_step:
            raise ValueError(
                f"Shotgrid does not have Pipeline Step {ay_entity.name}"
            )

    sg_parent_id = ay_entity.parent.attribs.get(SHOTGRID_ID_ATTRIB)
    sg_parent_type = ay_entity.parent.attribs.get(SHOTGRID_TYPE_ATTRIB)

    if not (sg_parent_id and sg_parent_type):
        raise ValueError(
                "Parent does not exist in Shotgrid!"
                f"{sg_parent_type} <{sg_parent_id}>"
            )

    parent_field = get_sg_entity_parent_field(
        sg_session,
        sg_project,
        sg_type,
    )

    if parent_field.lower() == "project":
        data = {
            "project": sg_project,
            sg_field_name: ay_entity.name,
            CUST_FIELD_CODE_ID: ay_entity.id,
        }

    else:
        if ay_entity.entity_type == "task":
            data = {
                "project": sg_project,
                "entity": {"type": sg_parent_type, "id": int(sg_parent_id)},
                sg_field_name: ay_entity.name,
                CUST_FIELD_CODE_ID: ay_entity.id,
                "step": sg_step
            }
        else:
            data = {
                "project": sg_project,
                parent_field: {"type": sg_parent_type, "id": int(sg_parent_id)},
                sg_field_name: ay_entity.name,
                CUST_FIELD_CODE_ID: ay_entity.id,
            }

    logging.debug(f"Creating Shotgrid entity {sg_type} with data: {data}")

    return sg_session.create(sg_type, data)


