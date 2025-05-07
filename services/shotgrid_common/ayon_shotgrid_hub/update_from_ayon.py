"""Module that handles creation, update or removal of SG entities based on AYON events.
"""
from typing import Dict, List, Any

import shotgun_api3

import ayon_api

from utils import (
    get_sg_statuses,
    get_sg_tags,
    get_sg_custom_attributes_data,
    create_new_sg_entity
)
from constants import (
    CUST_FIELD_CODE_ID,  # Shotgrid Field for the AYON ID.
    SHOTGRID_ID_ATTRIB,  # AYON Entity Attribute.
    SHOTGRID_TYPE_ATTRIB,  # AYON Entity Attribute.
)

from utils import get_logger


log = get_logger(__file__)


def create_sg_entity_from_ayon_event(
    ayon_event: Dict,
    sg_session: shotgun_api3.Shotgun,
    ayon_entity_hub: ayon_api.entity_hub.EntityHub,
    sg_project: Dict,
    sg_enabled_entities: List[str],
    sg_project_code_field: [str],
    custom_attribs_map: Dict[str, str],
    addon_settings: Dict[str, Any],
):
    """Create a Shotgrid entity from an AYON event.

    Args:
        sg_event (dict): AYON event.
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        sg_project (dict): The Shotgrid project.
        sg_enabled_entities (list): List of Shotgrid entities to be enabled.
        sg_project_code_field (str): 'code' most likely
        custom_attribs_map (dict): Dictionary that maps a list of attribute names from
            AYON to Shotgrid.

    Returns:
        ay_entity (ayon_api.entity_hub.EntityHub.Entity): The newly
            created entity.
    """
    ay_id = ayon_event["summary"]["entityId"]
    ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
        ay_id, ["folder", "task", "version"])

    if not ay_entity:
        raise ValueError(
            "Event has a non existent entity? "
            f"{ayon_event['summary']['entityId']}"
        )

    sg_id = ay_entity.attribs.get("shotgridId")
    sg_type = ay_entity.attribs.get("shotgridType")

    if not sg_type:
        if ay_entity.entity_type == "task":
            sg_type = "Task"
        elif ay_entity.entity_type == "version":
            sg_type = "Version"
        else:
            sg_type = ay_entity.folder_type

    sg_entity = None

    if sg_id and sg_type:
        sg_entity = sg_session.find_one(sg_type, [["id", "is", int(sg_id)]])

    if sg_entity:
        log.warning(f"Entity {sg_entity} already exists in Shotgrid!")
        return

    try:
        sg_parent_entity = _get_sg_parent_entity(
            sg_session, ay_entity, ayon_event)

        sg_entity = create_new_sg_entity(
            ay_entity,
            sg_session,
            sg_project,
            sg_parent_entity,
            sg_enabled_entities,
            sg_project_code_field,
            custom_attribs_map,
            addon_settings,
            ayon_event["project"]
        )
        if not sg_entity:
            log.warning(f"Couldn't create SG entity for '{ay_id}")

        if (
            ay_entity.entity_type == "folder"
            and ay_entity.folder_type == "AssetCategory"
        ):
            # AssetCategory is special, we don't want to create it in Shotgrid
            # but we need to assign Shotgrid ID and Type to it
            sg_entity = {
                "id": ay_entity.name.lower(),
                "type": "AssetCategory"
            }

        if not sg_entity:
            if hasattr(ay_entity, "folder_type"):
                log.warning(
                    f"Unable to create `{ay_entity.folder_type}` <{ay_id}> "
                    "in Shotgrid!"
                )
            else:
                log.warning(
                    f"Unable to create `{ay_entity.entity_type}` <{ay_id}> "
                    "in Shotgrid!"
                )
            return

        sg_id = sg_entity["attribs"]["shotgridId"]
        sg_type = sg_entity["attribs"]["shotgridType"]
        log.info(f"Created Shotgrid entity: {sg_id} of {sg_type}")

        ay_entity.attribs.set(
            SHOTGRID_ID_ATTRIB,
            sg_id
        )
        ay_entity.attribs.set(
            SHOTGRID_TYPE_ATTRIB,
            sg_type
        )
        ayon_entity_hub.commit_changes()
    except Exception:
        log.error(
            f"Unable to create {sg_type} <{ay_id}> in Shotgrid!",
            exc_info=True
        )


def _get_sg_parent_entity(sg_session, ay_entity, ayon_event):
    """Returns SG parent for currently created ay_entity

    Returns:
        Dict[str, str]  {"id": XXXX, "type": "Asset|.."}
    """
    if ay_entity.entity_type == "version":
        folder_id = ay_entity.parent.parent.id
        ayon_asset = ayon_api.get_folder_by_id(
            ayon_event["project"], folder_id)

        if not ayon_asset:
            raise ValueError(f"Not fount '{folder_id}'")

        sg_parent_id = ayon_asset["attrib"].get(SHOTGRID_ID_ATTRIB)
        sg_parent_type = ayon_asset["attrib"].get(SHOTGRID_TYPE_ATTRIB)
    else:
        sg_parent_id = ay_entity.parent.attribs.get(SHOTGRID_ID_ATTRIB)
        sg_parent_type = ay_entity.parent.attribs.get(SHOTGRID_TYPE_ATTRIB)
    sg_parent_entity = sg_session.find_one(
        sg_parent_type,
        filters=[[
            "id",
            "is",
            int(sg_parent_id)
        ]]
    )
    return sg_parent_entity


def update_sg_entity_from_ayon_event(
    ayon_event: Dict,
    sg_session: shotgun_api3.Shotgun,
    ayon_entity_hub: ayon_api.entity_hub.EntityHub,
    custom_attribs_map: Dict[str, str],
    addon_settings: Dict[str, Any],
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
    ay_id = ayon_event["summary"]["entityId"]
    ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
        ay_id, ["folder", "task"])

    if not ay_entity:
        raise ValueError(
            "Event has a non existent entity? "
            f"{ayon_event['summary']['entityId']}"
        )

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

        if isinstance(new_attribs, dict):
            # If payload newValue is a dict it means it's an attribute update
            # but this only apply to case were attribs key is in the
            # newValue dict
            if "attribs" in new_attribs:
                new_attribs = new_attribs["attribs"]

        # Otherwise it's a tag/status update
        elif ayon_event["topic"].endswith("status_changed"):
            sg_statuses = get_sg_statuses(sg_session, sg_entity_type)
            ay_statuses = {
                status.name: status.short_name
                for status in  ayon_entity_hub.project_entity.statuses
            }
            short_name = ay_statuses.get(new_attribs)
            if short_name in sg_statuses:
                new_attribs = {"status": short_name}
            else:
                log.error(
                    f"Unable to update '{sg_entity_type}' with status "
                    f"'{new_attribs}' in Shotgrid as it's not compatible! "
                    f"It should be one of: {sg_statuses}"
                )
                return
        elif ayon_event["topic"].endswith("tags_changed"):
            tags_event_list = new_attribs
            new_attribs = {"tags": []}
            sg_tags = get_sg_tags(sg_session)
            for tag_name in tags_event_list:
                if tag_name.lower() in sg_tags:
                    tag_id = sg_tags[tag_name]
                else:
                    log.info(
                        f"Tag '{tag_name}' not found in ShotGrid, "
                        "creating a new one."
                    )
                    new_tag = sg_session.create("Tag", {'name': tag_name})
                    tag_id = new_tag["id"]

                new_attribs["tags"].append(
                    {"name": tag_name, "id": tag_id, "type": "Tag"}
                )
        elif ayon_event["topic"].endswith("assignees_changed"):
            sg_assignees = []
            for user_name in new_attribs:
                ayon_user = ayon_api.get_user(user_name)
                if not ayon_user or not ayon_user["data"].get("sg_user_id"):
                    log.warning(f"User {user_name} is not synched to SG yet.")
                    continue
                sg_assignees.append(
                    {"type": "HumanUser",
                     "id": ayon_user["data"]["sg_user_id"]}
                )
            new_attribs = {"assignees": sg_assignees}
        else:
            log.warning(
                "Unknown event type, skipping update of custom attribs.")
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
        log.info(f"Updated ShotGrid entity: {sg_entity}")
        return sg_entity
    except Exception:
        log.error(
            f"Unable to update {sg_entity_type} <{sg_id}> in ShotGrid!",
            exc_info=True
        )


def remove_sg_entity_from_ayon_event(
    ayon_event: Dict,
    sg_session: shotgun_api3.Shotgun
):
    """Try to remove a Shotgrid entity from an AYON event.

    Args:
        ayon_event (dict): The `meta` key from a Shotgrid Event.
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
    """
    ay_id = ayon_event["payload"]["entityData"]["id"]
    log.debug(f"Removing Shotgrid entity: {ayon_event['payload']}")

    sg_id = ayon_event["payload"]["entityData"]["attrib"].get("shotgridId")

    if not sg_id:
        ay_entity_path = ayon_event["payload"]["entityData"]["path"]
        log.warning(
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
        log.warning(
            f"Unable to find AYON entity with id '{ay_id}' in Shotgrid.")
        return

    sg_id = sg_entity["id"]

    try:
        sg_session.delete(sg_type, int(sg_id))
        log.info(f"Retired Shotgrid entity: {sg_type} <{sg_id}>")
    except Exception:
        log.error(
            f"Unable to delete {sg_type} <{sg_id}> in Shotgrid!",
            exc_info=True
        )

