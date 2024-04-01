"""Module that handles creation, update or removal of AYON entities based on SG Events.

The updates come through `meta` dictionaries such as:
"meta": {
    "id": 1274,
    "type": "entity_retirement",
    "entity_id": 1274,
    "class_name": "Shot",
    "entity_type": "Shot",
    "display_name": "bunny_099_012",
    "retirement_date": "2023-03-31 15:26:16 UTC"
}

And most of the times it fetches the SG entity as an Ayon dict like:
{
    "label": label,
    "name": name,
    SHOTGRID_ID_ATTRIB: shotgrid id,
    CUST_FIELD_CODE_ID: ayon id stored in Shotgrid,
    CUST_FIELD_CODE_SYNC: sync status stored in shotgrid,
    "type": the entity type,
}

"""

from utils import (
    get_asset_category,
    get_sg_entity_as_ay_dict,
    get_sg_entity_parent_field
)
from constants import (
    CUST_FIELD_CODE_ID,  # Shotgrid Field for the Ayon ID.
    SHOTGRID_ID_ATTRIB,  # Ayon Entity Attribute.
    SHOTGRID_TYPE_ATTRIB,  # Ayon Entity Attribute.
    SHOTGRID_REMOVED_VALUE
)

from nxtools import logging


def create_ay_entity_from_sg_event(
    sg_event,
    sg_project,
    sg_session,
    ayon_entity_hub,
    sg_enabled_entites,
    project_code_field,
    custom_attribs_map=None,
):
    """Create an AYON entity from a Shotgrid Event.

    Args:
        sg_event (dict): The `meta` key from a Shotgrid Event.
        sg_project (dict): The Shotgrid project.
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        sg_enabled_entities (list[str]): List of entity strings enabled.
        project_code_field (str): The Shotgrid project code field.
        custom_attribs_map (dict): Dictionary that maps a list of attribute names from
            Ayon to Shotgrid.

    Returns:
        ay_entity (ayon_api.entity_hub.EntityHub.Entity): The newly created entity.
    """
    sg_parent_field = get_sg_entity_parent_field(
        sg_session,
        sg_project,
        sg_event["entity_type"],
        sg_enabled_entites,
    )
    extra_fields = [sg_parent_field]

    if sg_event["entity_type"] == "Asset":
        extra_fields.append("sg_asset_type")
        sg_parent_field = "sg_asset_type"

    sg_entity_dict = get_sg_entity_as_ay_dict(
        sg_session,
        sg_event["entity_type"],
        sg_event["entity_id"],
        project_code_field,
        extra_fields=extra_fields,
        custom_attribs_map=custom_attribs_map,
    )
    logging.debug(f"SG Entity as Ayon dict: {sg_entity_dict}")
    if not sg_entity_dict:
        logging.warning(
            "Entity {sg_event['entity_type']} <{sg_event['entity_id']}> "
            "no longer exists in Shotgrid, aborting..."
        )
        return

    if sg_entity_dict["data"].get(CUST_FIELD_CODE_ID):
        # Revived entity, check if it's still in the Server
        ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
            sg_entity_dict["data"].get(CUST_FIELD_CODE_ID),
            [sg_entity_dict["type"]]
        )

        if ay_entity:
            logging.debug(f"SG Entity exists in AYON.")
            # Ensure Ayon Entity has the correct Shotgrid ID
            ay_shotgrid_id = sg_entity_dict["attribs"].get(SHOTGRID_ID_ATTRIB, "")
            if ay_entity.attribs.get_attribute(SHOTGRID_ID_ATTRIB).value != str(ay_shotgrid_id):
                ay_entity.attribs.set(
                    SHOTGRID_ID_ATTRIB,
                    ay_shotgrid_id
                )
                ay_entity.attribs.set(
                    SHOTGRID_TYPE_ATTRIB,
                    sg_entity_dict["type"]
                )
            
            # TODO: Make sure attributes are on sync?
            # if custom_attribs_map:
            #     for ay_attr in custom_attribs_map.keys():
            #         sg_value = sg_entity_dict["data"].get(ay_attr)

            #         # If no value in SG entity skip
            #         if not sg_value:
            #             continue
                    
            #         ay_entity.attribs.set(ay_attr, sg_value)

            return ay_entity

    if sg_entity_dict["data"][sg_parent_field] is None:
        # Parent is the project
        logging.debug(f"SG Parent is the Project: {sg_project}")
        ay_parent_entity = ayon_entity_hub.project_entity
    else:
        if sg_entity_dict["attribs"][SHOTGRID_TYPE_ATTRIB] == "Asset" and sg_entity_dict["data"].get("sg_asset_type"):
            logging.debug(f"SG Parent is an Asset category.")

            ay_parent_entity = get_asset_category(
                ayon_entity_hub,
                ayon_entity_hub.project_entity,
                sg_entity_dict.get("sg_asset_type").lower()
            )

        else:
            # Find parent entity ID
            sg_parent_entity_dict = get_sg_entity_as_ay_dict(
                sg_session,
                sg_entity_dict["data"][sg_parent_field]["type"],
                sg_entity_dict["data"][sg_parent_field]["id"],
                project_code_field,
            )

            logging.debug(f"SG Parent entity: {sg_parent_entity_dict}")
            ay_parent_entity = ayon_entity_hub.get_or_query_entity_by_id(
                sg_parent_entity_dict["data"].get(CUST_FIELD_CODE_ID),
                ["task" if sg_parent_entity_dict["data"].get(CUST_FIELD_CODE_ID).lower() == "task" else "folder"]
            )

    if not ay_parent_entity:
        # This really should be an edge  ase, since any parent event would
        # happen before this... but hey
        raise ValueError("Parent does not exist in Ayon, try doing a Project Sync.")

    if sg_entity_dict["type"].lower() == "task":
        ay_entity = ayon_entity_hub.add_new_task(
            sg_entity_dict["task_type"],
            name=sg_entity_dict["name"],
            label=sg_entity_dict["label"],
            entity_id=sg_entity_dict["data"][CUST_FIELD_CODE_ID],
            parent_id=ay_parent_entity.id,
            attribs=sg_entity_dict["attribs"]
        )
    else:
        ay_entity = ayon_entity_hub.add_new_folder(
            sg_entity_dict["folder_type"],
            name=sg_entity_dict["name"],
            label=sg_entity_dict["label"],
            entity_id=sg_entity_dict["data"][CUST_FIELD_CODE_ID],
            parent_id=ay_parent_entity.id,
            attribs=sg_entity_dict["attribs"]
        )

    logging.debug(f"Created new AYON entity: {ay_entity}")
    ay_entity.attribs.set(
        SHOTGRID_ID_ATTRIB,
        sg_entity_dict["attribs"].get(SHOTGRID_ID_ATTRIB, "")
    )
    ay_entity.attribs.set(
        SHOTGRID_TYPE_ATTRIB,
        sg_entity_dict["attribs"].get(SHOTGRID_TYPE_ATTRIB, "")
    )

    try:
        ayon_entity_hub.commit_changes()

        sg_session.update(
            sg_entity_dict["attribs"][SHOTGRID_TYPE_ATTRIB],
            sg_entity_dict["attribs"][SHOTGRID_ID_ATTRIB],
            {
                CUST_FIELD_CODE_ID: ay_entity.id
            }
        )
    except Exception as e:
        logging.error(e)
        pass

    return ay_entity


def update_ayon_entity_from_sg_event(
    sg_event,
    sg_session,
    ayon_entity_hub,
    project_code_field,
    custom_attribs_map
):
    """Try to update an entity in Ayon.

    Args:
        sg_event (dict): The `meta` key from a Shotgrid Event.
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        project_code_field (str): The Shotgrid project code field.
        custom_attribs_map (dict): Dictionary of extra attributes to store in the SG entity.

    Returns:
        ay_entity (ayon_api.entity_hub.EntityHub.Entity): The modified entity.

    """
    sg_entity_dict = get_sg_entity_as_ay_dict(
        sg_session,
        sg_event["entity_type"],
        sg_event["entity_id"],
        project_code_field,
        custom_attribs_map=custom_attribs_map
    )

    if not sg_entity_dict["data"].get(CUST_FIELD_CODE_ID):
        logging.warning("Shotgrid Missing Ayon ID")

    ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
        sg_entity_dict["data"].get(CUST_FIELD_CODE_ID),
        [sg_entity_dict["type"]]
    )

    if not ay_entity:
        logging.error("Unable to update a non existing entity.")
        raise ValueError("Unable to update a non existing entity.")

    logging.debug(f"Updating Ayon Entity: {ay_entity.name}")

    if int(ay_entity.attribs.get_attribute(SHOTGRID_ID_ATTRIB).value) != int(sg_entity_dict["attribs"].get(SHOTGRID_ID_ATTRIB)):
        logging.error("Mismatching Shotgrid IDs, aborting...")
        raise ValueError("Mismatching Shotgrid IDs, aborting...")

    logging.debug("Updating Ayon entity with '%s'" % sg_entity_dict)
    ay_entity.name = sg_entity_dict["name"]
    ay_entity.label = sg_entity_dict["label"]

    for attr, attr_value in sg_entity_dict["attribs"].items():
        # TODO: add support for tags
        if attr == "tags":
            continue

        ay_attr = next(
            (
                ay_attr for ay_attr in custom_attribs_map.keys()
                if ay_attr == attr
            ),
            None
        )
        if attr == "status":
            ay_entity.status = attr_value
        elif ay_attr:
            logging.info(
                f"Setting attribute {ay_attr} with value {attr_value}")
            ay_entity.attribs.set(ay_attr, attr_value)

    ayon_entity_hub.commit_changes()

    if sg_entity_dict["data"].get(CUST_FIELD_CODE_ID) != ay_entity.id:
        sg_session.update(
            sg_entity_dict["attribs"][SHOTGRID_TYPE_ATTRIB],
            sg_entity_dict["attribs"][SHOTGRID_ID_ATTRIB],
            {
                CUST_FIELD_CODE_ID: ay_entity.id
            }
        )

    return ay_entity


def remove_ayon_entity_from_sg_event(sg_event, sg_session, ayon_entity_hub, project_code_field):
    """Try to remove an entity in Ayon.

    Args:
        sg_event (dict): The `meta` key from a Shotgrid Event.
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
    """
    sg_entity_dict = get_sg_entity_as_ay_dict(
        sg_session,
        sg_event["entity_type"],
        sg_event["entity_id"],
        project_code_field,
        retired_only=True
    )

    logging.debug(f"SG Entity as Ay dict: {sg_entity_dict}")
    if not sg_entity_dict:
        logging.warning(f"Entity {sg_event['entity_type']} <{sg_event['entity_id']}> no longer exists in SG.")
        raise ValueError(f"Entity {sg_event['entity_type']} <{sg_event['entity_id']}> no longer exists in SG.")

    if not sg_entity_dict["data"].get(CUST_FIELD_CODE_ID):
        logging.warning("Shotgrid Missing Ayon ID")
        raise ValueError("Shotgrid Missing Ayon ID")

    ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
        sg_entity_dict["data"].get(CUST_FIELD_CODE_ID),
        ["task" if sg_entity_dict.get("type").lower() == "task" else "folder"]
    )

    if not ay_entity:
        logging.error("Unable to update a non existing entity.")
        raise ValueError("Unable to update a non existing entity.")

    if sg_entity_dict["data"].get(CUST_FIELD_CODE_ID) != ay_entity.id:
        logging.error("Mismatching Shotgrid IDs, aborting...")
        raise ValueError("Mismatching Shotgrid IDs, aborting...")

    if not ay_entity.immutable_for_hierarchy:
        logging.info(f"Deleting AYON entity: {ay_entity}")
        ayon_entity_hub.delete_entity(ay_entity)
    else:
        logging.info("Entity is immutable.")
        ay_entity.attribs.set(SHOTGRID_ID_ATTRIB, SHOTGRID_REMOVED_VALUE)

    ayon_entity_hub.commit_changes()
