"""Module that handles creation, update or removal of AYON entities
based on ShotGrid Events.

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

And most of the times it fetches the ShotGrid entity as an AYON dict like:
{
    "label": label,
    "name": name,
    SHOTGRID_ID_ATTRIB: ShotGrid id,
    CUST_FIELD_CODE_ID: ayon id stored in ShotGrid,
    CUST_FIELD_CODE_SYNC: sync status stored in ShotGrid,
    "type": the entity type,
}

"""
import collections

import shotgun_api3
import ayon_api
from typing import Dict, List, Optional, Any

from utils import (
    create_new_ayon_entity,
    get_asset_category,
    get_shot_category,
    get_sequence_category,
    get_sg_entity_as_ay_dict,
    get_sg_entity_parent_field,
    update_ay_entity_custom_attributes,
)
from constants import (
    CUST_FIELD_CODE_ID,  # ShotGrid Field for the AYON ID.
    SHOTGRID_ID_ATTRIB,  # AYON Entity Attribute.
    SHOTGRID_TYPE_ATTRIB,  # AYON Entity Attribute.
    SHOTGRID_REMOVED_VALUE,  # Value for removed entities.
    SG_RESTRICTED_ATTR_FIELDS,
)

from utils import get_logger


log = get_logger(__file__)


def create_ay_entity_from_sg_event(
    sg_event: Dict,
    sg_project: Dict,
    sg_session: shotgun_api3.Shotgun,
    ayon_entity_hub: ayon_api.entity_hub.EntityHub,
    sg_enabled_entities: List[str],
    project_code_field: str,
    custom_attribs_map: Optional[Dict[str, str]] = None,
    addon_settings: Optional[Dict[str, str]] = None
):
    """Create an AYON entity from a ShotGrid Event.

    Args:
        sg_event (dict): The `meta` key from a ShotGrid Event.
        sg_project (dict): The ShotGrid project.
        sg_session (shotgun_api3.Shotgun): The ShotGrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        sg_enabled_entities (list[str]): List of entity strings enabled.
        project_code_field (str): The Shotgrid project code field.
        custom_attribs_map (Optional[dict]): A dictionary that maps ShotGrid
            attributes to Ayon attributes.
        addon_settings (Optional[dict]): A dictionary of Settings

    Returns:
        ay_entity (ayon_api.entity_hub.EntityHub.Entity): The newly
            created entity.
    """
    default_task_type = addon_settings[
        "compatibility_settings"]["default_task_type"]
    sg_parent_field = get_sg_entity_parent_field(
        sg_session,
        sg_project,
        sg_event["entity_type"],
        sg_enabled_entities,
    )

    extra_fields = [sg_parent_field]

    if sg_event["entity_type"] == "Shot":
        sg_parent_field = "sg_sequence"

    sg_ay_dict = get_sg_entity_as_ay_dict(
        sg_session,
        sg_event["entity_type"],
        sg_event["entity_id"],
        project_code_field,
        default_task_type,
        custom_attribs_map=custom_attribs_map,
        extra_fields=extra_fields,
    )
    log.debug(f"ShotGrid Entity as AYON dict: {sg_ay_dict}")
    if not sg_ay_dict:
        log.warning(
            f"Entity {sg_event['entity_type']} <{sg_event['entity_id']}> "
            "no longer exists in ShotGrid, aborting..."
        )
        return

    ayon_id_stored_in_sg = sg_ay_dict["data"].get(CUST_FIELD_CODE_ID)
    if ayon_id_stored_in_sg:
        # Revived entity, check if it's still in the Server
        ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
            ayon_id_stored_in_sg,
            [sg_ay_dict["type"]]
        )

        if ay_entity:
            log.debug("ShotGrid Entity exists in AYON.")
            # Ensure AYON Entity has the correct ShotGrid ID
            ay_entity = _update_sg_id(
                ay_entity, custom_attribs_map, sg_ay_dict)

            return ay_entity

    ay_parent_entity = None
    items_to_create = collections.deque()
    while ay_parent_entity is None:
        items_to_create.append(sg_ay_dict)
        ay_parent_entity = _get_ayon_parent_entity(
            ayon_entity_hub,
            project_code_field,
            sg_ay_dict,
            sg_parent_field,
            sg_project,
            sg_session,
            addon_settings
        )

        sg_parent = sg_ay_dict["data"].get(sg_parent_field)
        if not ay_parent_entity and not sg_parent:
            ay_parent_entity = ayon_entity_hub.project_entity

        if not ay_parent_entity:
            sg_ay_parent_dict = get_sg_entity_as_ay_dict(
                sg_session,
                sg_ay_dict["data"][sg_parent_field]["type"],
                sg_ay_dict["data"][sg_parent_field]["id"],
                project_code_field,
                default_task_type,
            )

            if sg_ay_parent_dict["attribs"].get("shotgridType") == "Asset":
                # re query to get proper parent assetType value
                # we cannot add 'sg_asset_type' to extra_fields directly as
                # task might be under shot/sequence
                extra_fields.append("sg_asset_type")

                sg_ay_parent_dict = get_sg_entity_as_ay_dict(
                    sg_session,
                    sg_ay_dict["data"][sg_parent_field]["type"],
                    sg_ay_dict["data"][sg_parent_field]["id"],
                    project_code_field,
                    default_task_type,
                    custom_attribs_map=custom_attribs_map,
                    extra_fields=extra_fields,
                )
                sg_parent_field = "sg_asset_type"
            sg_ay_dict = sg_ay_parent_dict

    while items_to_create:
        sg_ay_dict = items_to_create.pop()

        shotgrid_type = sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB]
        sg_parent_field = get_sg_entity_parent_field(
            sg_session,
            sg_project,
            shotgrid_type,
            sg_enabled_entities,
        )
        ay_parent_entity = _get_ayon_parent_entity(
            ayon_entity_hub,
            project_code_field,
            sg_ay_dict,
            sg_parent_field,
            sg_project,
            sg_session,
            addon_settings
        )

        ay_entity = create_new_ayon_entity(
            sg_session,
            ayon_entity_hub,
            ay_parent_entity,
            sg_ay_dict
        )

    return ay_entity


def _get_ayon_parent_entity(
    ayon_entity_hub,
    project_code_field,
    sg_ay_dict,
    sg_parent_field,
    sg_project,
    sg_session,
    addon_settings
):
    """Tries to find parent entity in AYON

    Args:
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        project_code_field (str): The Shotgrid project code field.
        sg_ay_dict (dict): The ShotGrid entity ready for AYON consumption.:
        sg_parent_field (str): 'project'|'sequence'
        sg_project (dict): The ShotGrid project.
        sg_session (shotgun_api3.Shotgun): The ShotGrid API session.
        addon_settings (Optional[dict]): A dictionary of Settings. Used to
            query location of custom folders (`shots`, `sequences`)

    Returns:
        ay_entity (ayon_api.entity_hub.EntityHub.Entity):
            FolderEntity|ProjectEntity
    """
    default_task_type = addon_settings[
        "compatibility_settings"]["default_task_type"]
    shotgrid_type = sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB]
    sg_parent = sg_ay_dict["data"].get(sg_parent_field)
    ay_parent_entity = None

    if (
        shotgrid_type == "Asset"
        and sg_ay_dict["data"].get("sg_asset_type")
    ):
        log.debug("ShotGrid Parent is an Asset category.")
        ay_parent_entity = get_asset_category(
            ayon_entity_hub,
            sg_ay_dict,
            addon_settings
        )

    elif(shotgrid_type == "Sequence"):
        log.info("ShotGrid Parent is an Sequence category.")
        ay_parent_entity = get_sequence_category(
            ayon_entity_hub,
            sg_ay_dict,
            addon_settings
        )

    elif(shotgrid_type == "Shot"):
        log.info("ShotGrid Parent is an Shot category.")
        ay_parent_entity = get_shot_category(
            ayon_entity_hub,
            sg_ay_dict,
            addon_settings
        )

    if ay_parent_entity is None:
        # INFO: Parent entity might not be added in SG so this needs to
        # be handled with optional way.
        if sg_parent is None:
            # Parent is the project
            log.debug(f"ShotGrid Parent is the Project: {sg_project}")
            ay_parent_entity = ayon_entity_hub.project_entity

        else:
            # Find parent entity ID
            sg_parent_entity_dict = get_sg_entity_as_ay_dict(
                sg_session,
                sg_parent["type"],
                sg_parent["id"],
                project_code_field,
                default_task_type,
            )

            log.debug(f"ShotGrid Parent entity: {sg_parent_entity_dict}")
            ay_parent_entity = ayon_entity_hub.get_or_query_entity_by_id(
                sg_parent_entity_dict["data"].get(CUST_FIELD_CODE_ID),
                [
                    (
                        "task"
                        if sg_parent_entity_dict["type"] == "task"
                        else "folder"
                    )
                ],
            )
    return ay_parent_entity


def _update_sg_id(ay_entity, custom_attribs_map, sg_ay_dict):
    ayon_entity_sg_id = str(
        ay_entity.attribs.get_attribute(SHOTGRID_ID_ATTRIB).value)
    # Ensure AYON Entity has the correct Shotgrid ID
    ay_shotgrid_id = str(
        sg_ay_dict["attribs"].get(SHOTGRID_ID_ATTRIB, ""))
    if ayon_entity_sg_id != ay_shotgrid_id:
        ay_entity.attribs.set(
            SHOTGRID_ID_ATTRIB,
            ay_shotgrid_id
        )
        ay_entity.attribs.set(
            SHOTGRID_TYPE_ATTRIB,
            sg_ay_dict["type"]
        )
    update_ay_entity_custom_attributes(
        ay_entity, sg_ay_dict, custom_attribs_map
    )

    return ay_entity


def update_ayon_entity_from_sg_event(
    sg_event: Dict,
    sg_project: Dict,
    sg_session: shotgun_api3.Shotgun,
    ayon_entity_hub: ayon_api.entity_hub.EntityHub,
    sg_enabled_entities: List[str],
    project_code_field: str,
    addon_settings: Dict[str, Any],
    custom_attribs_map: Optional[Dict[str, str]] = None,
):
    """Try to update an entity in AYON.

    Args:
        sg_event (dict): The `meta` key from a ShotGrid Event.
        sg_project (dict): The ShotGrid project.
        sg_session (shotgun_api3.Shotgun): The ShotGrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        sg_enabled_entities (list[str]): List of entity strings enabled.
        project_code_field (str): The ShotGrid project code field.
        addon_settings (dict): A dictionary of Settings.
        custom_attribs_map (dict): A dictionary that maps ShotGrid
            attributes to AYON attributes.

    Returns:
        ay_entity (ayon_api.entity_hub.EntityHub.Entity): The modified entity.

    """
    default_task_type = addon_settings[
        "compatibility_settings"]["default_task_type"]

    sg_ay_dict = get_sg_entity_as_ay_dict(
        sg_session,
        sg_event["entity_type"],
        sg_event["entity_id"],
        project_code_field,
        default_task_type,
        custom_attribs_map=custom_attribs_map
    )

    if not sg_ay_dict:
        log.warning(
            f"Entity {sg_event['entity_type']} <{sg_event['entity_id']}> "
            "no longer exists in ShotGrid, aborting..."
        )
        return

    # if the entity does not have an AYON ID, try to create it
    # and no need to update
    if not sg_ay_dict["data"].get(CUST_FIELD_CODE_ID):
        log.debug(f"Creating AYON Entity: {sg_ay_dict}")
        try:
            create_ay_entity_from_sg_event(
                sg_event,
                sg_project,
                sg_session,
                ayon_entity_hub,
                sg_enabled_entities,
                project_code_field,
                custom_attribs_map
            )
        except Exception:
            log.debug("AYON Entity could not be created", exc_info=True)
        return

    ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
        sg_ay_dict["data"].get(CUST_FIELD_CODE_ID),
        [sg_ay_dict["type"]]
    )

    if not ay_entity:
        raise ValueError("Unable to update a non existing entity.")

    # make sure the entity is not immutable
    if (
        ay_entity.immutable_for_hierarchy
        and sg_event["attribute_name"] in SG_RESTRICTED_ATTR_FIELDS
    ):
        raise ValueError("Entity is immutable, aborting...")

    # Ensure AYON Entity has the correct ShotGrid ID
    ayon_entity_sg_id = str(
        ay_entity.attribs.get(SHOTGRID_ID_ATTRIB, "")
    )
    sg_entity_sg_id = str(
        sg_ay_dict["attribs"].get(SHOTGRID_ID_ATTRIB, "")
    )
    log.debug(f"Updating AYON Entity: {ay_entity.name}")

    # We need to check for existence in `ayon_entity_sg_id` as it could be
    # that it's a new entity and it doesn't have a ShotGrid ID yet.
    if ayon_entity_sg_id and ayon_entity_sg_id != sg_entity_sg_id:
        log.error("Mismatching ShotGrid IDs, aborting...")
        raise ValueError("Mismatching ShotGrid IDs, aborting...")

    ay_entity.name = sg_ay_dict["name"]
    ay_entity.label = sg_ay_dict["label"]

    # TODO: Only update the updated fields in the event
    update_ay_entity_custom_attributes(
        ay_entity,
        sg_ay_dict,
        custom_attribs_map,
        ay_project=ayon_entity_hub.project_entity
    )

    ayon_entity_hub.commit_changes()

    if sg_ay_dict["data"].get(CUST_FIELD_CODE_ID) != ay_entity.id:
        sg_session.update(
            sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB],
            sg_ay_dict["attribs"][SHOTGRID_ID_ATTRIB],
            {
                CUST_FIELD_CODE_ID: ay_entity.id
            }
        )

    ay_entity.attribs.set(
        SHOTGRID_ID_ATTRIB,
        sg_ay_dict["attribs"].get(SHOTGRID_ID_ATTRIB, "")
    )
    ay_entity.attribs.set(
        SHOTGRID_TYPE_ATTRIB,
        sg_ay_dict["attribs"].get(SHOTGRID_TYPE_ATTRIB, "")
    )

    return ay_entity


def remove_ayon_entity_from_sg_event(
    sg_event: Dict,
    sg_session: shotgun_api3.Shotgun,
    ayon_entity_hub: ayon_api.entity_hub.EntityHub,
    project_code_field: str,
    addon_settings: Dict[str, Any],
):
    """Try to remove an entity in AYON.

    Args:
        sg_event (dict): The `meta` key from a ShotGrid Event.
        sg_session (shotgun_api3.Shotgun): The ShotGrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        project_code_field (str): The ShotGrid field that contains the AYON ID.
        addon_settings (dict): A dictionary of Settings.
    """
    default_task_type = addon_settings[
        "compatibility_settings"]["default_task_type"]

    sg_ay_dict = get_sg_entity_as_ay_dict(
        sg_session,
        sg_event["entity_type"],
        sg_event["entity_id"],
        project_code_field,
        default_task_type,
        retired_only=True
    )

    if not sg_ay_dict:
        sg_ay_dict = get_sg_entity_as_ay_dict(
            sg_session,
            sg_event["entity_type"],
            sg_event["entity_id"],
            project_code_field,
            default_task_type,
            retired_only=False,
        )
        if sg_ay_dict:
            log.info(
                f"No need to remove entity {sg_event['entity_type']} "
                f"<{sg_event['entity_id']}>, it's not retired anymore."
            )
            return
        else:
            log.warning(
                f"Entity {sg_event['entity_type']} <{sg_event['entity_id']}> "
                "no longer exists in ShotGrid."
            )

    if not sg_ay_dict["data"].get(CUST_FIELD_CODE_ID):
        log.warning(
            "Entity does not have an AYON ID, aborting..."
        )
        return

    ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
        sg_ay_dict["data"].get(CUST_FIELD_CODE_ID),
        ["task" if sg_ay_dict.get("type").lower() == "task" else "folder"]
    )

    if not ay_entity:
        raise ValueError("Unable to update a non existing entity.")

    if sg_ay_dict["data"].get(CUST_FIELD_CODE_ID) != ay_entity.id:
        raise ValueError("Mismatching ShotGrid IDs, aborting...")

    if not ay_entity.immutable_for_hierarchy:
        log.info(f"Deleting AYON entity: {ay_entity}")
        ayon_entity_hub.delete_entity(ay_entity)
    else:
        log.info("Entity is immutable.")
        ay_entity.attribs.set(SHOTGRID_ID_ATTRIB, SHOTGRID_REMOVED_VALUE)

    ayon_entity_hub.commit_changes()
