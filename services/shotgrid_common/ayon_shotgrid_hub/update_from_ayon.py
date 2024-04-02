"""Module that handles creation, update or removal of SG entities based on AYON events.
"""

from utils import (
    get_sg_entity_parent_field,
    get_sg_statuses,
    get_sg_custom_attributes_data
)
from constants import (
    CUST_FIELD_CODE_ID,  # Shotgrid Field for the Ayon ID.
    SHOTGRID_ID_ATTRIB,  # Ayon Entity Attribute.
    SHOTGRID_TYPE_ATTRIB,  # Ayon Entity Attribute.
)

from nxtools import logging, log_traceback


def create_sg_entity_from_ayon_event(
    ayon_event,
    sg_session,
    ayon_entity_hub,
    sg_project,
    sg_enabled_entities,
    custom_attribs_map,
):
    """Create a Shotgrid entity from an AYON event.

    Args:
        sg_event (dict): AYON event.
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        sg_project (dict): The Shotgrid project.
        sg_enabled_entities (list): List of Shotgrid entities to be enabled.
        custom_attribs_map (dict): Dictionary that maps a list of attribute names from
            Ayon to Shotgrid.

    Returns:
        ay_entity (ayon_api.entity_hub.EntityHub.Entity): The newly
            created entity.
    """
    logging.debug(f"Processing event {ayon_event}")

    ay_id = ayon_event["summary"]["entityId"]
    ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
        ay_id, ["folder", "task"])

    if not ay_entity:
        raise ValueError(
            "Event has a non existant entity? "
            f"{ayon_event['summary']['entityId']}"
        )

    sg_id = ay_entity.attribs.get("shotgridId")
    sg_type = ay_entity.attribs.get("shotgridType")

    if not sg_type:
        if ay_entity.entity_type == "task":
            sg_type = "Task"
        else:
            sg_type = ay_entity.folder_type

    sg_entity = None

    logging.debug(f"Creating {ay_entity} ({sg_type} <{ay_id}>) in Shotgrid.")

    if sg_id and sg_type:
        logging.debug(f"Querying Shotgrid for {sg_type} <{sg_id}>")
        sg_entity = sg_session.find_one(sg_type, [["id", "is", int(sg_id)]])

    if sg_entity:
        logging.warning(f"Entity {sg_entity} already exists in Shotgrid!")
        return

    try:
        sg_entity = _create_sg_entity(
            sg_session,
            ay_entity,
            sg_project,
            sg_type,
            sg_enabled_entities,
            custom_attribs_map,
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


def update_sg_entity_from_ayon_event(
    ayon_event,
    sg_session,
    ayon_entity_hub,
    custom_attribs_map,
):
    """Try to update a Shotgrid entity from an AYON event.

    Args:
        sg_event (dict): The `meta` key from a Shotgrid Event.
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        custom_attribs_map (dict): A mapping of custom attributes to update.

    Returns:
        sg_entity (dict): The modified Shotgrid entity.

    """
    logging.debug(f"Processing event {ayon_event}")
    ay_id = ayon_event["summary"]["entityId"]
    ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
        ay_id, ["folder", "task"])

    if not ay_entity:
        raise ValueError(
            "Event has a non existent entity? "
            f"{ayon_event['summary']['entityId']}"
        )

    logging.debug(f"Processing entity {ay_entity}")

    sg_id = ay_entity.attribs.get("shotgridId")
    sg_entity_type = ay_entity.attribs.get("shotgridType")

    try:
        sg_field_name = "code"
        if ay_entity["entity_type"] == "task":
            sg_field_name = "content"

        data_to_update = {
            sg_field_name: ay_entity["name"],
            CUST_FIELD_CODE_ID: ay_entity["id"]
        }
        # Add any possible new values to update
        new_attribs = ayon_event["payload"].get("newValue")
        # If payload newValue is a dict it means it's an attribute update
        if isinstance(new_attribs, dict):
            new_attribs = {"attribs": new_attribs}
        # Otherwise it's a tag/status update
        else:
            if ayon_event["topic"].endswith("status_changed"):
                sg_statuses = get_sg_statuses(sg_session, sg_entity_type)
                for sg_status_code, sg_status_name in sg_statuses.items():
                    if new_attribs.lower() == sg_status_name.lower():
                        new_attribs = {"status": sg_status_code}
                        break
                else:
                    logging.error(
                        f"Unable to update '{sg_entity_type}' with status "
                        f"'{new_attribs}' in Shotgrid as it's not compatible! "
                        f"It should be one of: {sg_statuses}"
                    )
                    return
            elif ayon_event["topic"].endswith("tags_changed"):
                new_attribs = {"tags": new_attribs}
            else:
                logging.warning("Unknown event type, skipping update of custom attribs.")
                new_attribs = None

        if new_attribs:
            data_to_update.update(get_sg_custom_attributes_data(
                sg_session,
                new_attribs,
                sg_entity_type,
                custom_attribs_map
            ))

        sg_entity = sg_session.update(
            sg_entity_type,
            int(sg_id),
            data_to_update
        )
        logging.info(f"Updated Shotgrid entity: {sg_entity}")
        return sg_entity
    except Exception as e:
        logging.error(f"Unable to update {sg_entity_type} <{sg_id}> in Shotgrid!")
        log_traceback(e)


def remove_sg_entity_from_ayon_event(ayon_event, sg_session, ayon_entity_hub):
    """Try to remove a Shotgrid entity from an AYON event.

    Args:
        ayon_event (dict): The `meta` key from a Shotgrid Event.
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
    """
    logging.debug(f"Processing event {ayon_event}")
    ay_id = ayon_event["payload"]["entityData"]["id"]
    ay_entity_path = ayon_event["payload"]["entityData"]["path"]
    sg_id = ayon_event["payload"]["entityData"]["attrib"].get("shotgridId")

    if not sg_id:
        logging.warning(
            f"Entity '{ay_entity_path}' does not have a "
            "ShotGrid ID to remove."
        )
        return

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
        logging.warning(
            f"Unable to find Ayon entity with id '{ay_id}' in Shotgrid.")
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
    sg_enabled_entities,
    custom_attribs_map,
):
    """ Create a new Shotgrid entity.

    Args:
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
        ay_entity (dict): The AYON entity.
        sg_project (dict): The Shotgrid Project.
        sg_type (str): The Shotgrid type of the new entity.
        sg_enabled_entities (list): List of Shotgrid entities to be enabled.
        custom_attribs_map (dict): Dictionary of extra attributes to store in the SG entity.
    """
    sg_field_name = "code"
    sg_step = None

    sg_parent_id = ay_entity.parent.attribs.get(SHOTGRID_ID_ATTRIB)
    sg_parent_type = ay_entity.parent.attribs.get(SHOTGRID_TYPE_ATTRIB)

    if not (sg_parent_id and sg_parent_type):
        raise ValueError(
                "Parent does not exist in Shotgrid!"
                f"{sg_parent_type} <{sg_parent_id}>"
            )

    if ay_entity.entity_type == "task":
        sg_field_name = "content"

        step_query_filters = [["code", "is", ay_entity.task_type]]

        if sg_parent_type in ["Asset", "Shot"]:
            step_query_filters.append(
                ["entity_type", "is", sg_parent_type]
            )

        sg_step = sg_session.find_one(
            "Step",
            filters=step_query_filters,
        )

        if not sg_step:
            raise ValueError(
                f"Unable to create Task {ay_entity.task_type} {ay_entity}\n"
                f"-> Shotgrid is missing Pipeline Step {ay_entity.task_type}"
            )

    parent_field = get_sg_entity_parent_field(
        sg_session,
        sg_project,
        sg_type,
        sg_enabled_entities
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
                sg_field_name: ay_entity.label,
                CUST_FIELD_CODE_ID: ay_entity.id,
                "step": sg_step
            }
        else:
            data = {
                "project": sg_project,
                parent_field: {
                    "type": sg_parent_type,
                    "id": int(sg_parent_id)
                },
                sg_field_name: ay_entity.name,
                CUST_FIELD_CODE_ID: ay_entity.id,
            }

    # Fill up data with any extra attributes from Ayon we want to sync to SG
    data.update(get_sg_custom_attributes_data(
        sg_session,
        ay_entity,
        sg_type,
        custom_attribs_map
    ))

    logging.debug(f"Creating Shotgrid entity {sg_type} with data: {data}")

    try:
        sg_entity = sg_session.create(sg_type, data)
        return sg_entity
    except Exception as e:
        logging.error(
            f"Unable to create SG entity {sg_type} with data: {data}")
        log_traceback(e)
        raise e
