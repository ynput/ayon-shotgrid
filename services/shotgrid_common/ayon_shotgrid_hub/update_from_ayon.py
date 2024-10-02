"""Module that handles creation, update or removal of SG entities based on AYON events.
"""
import shotgun_api3
import ayon_api
from typing import Dict, List, Union

from ayon_api.entity_hub import (
    ProjectEntity,
    TaskEntity,
    FolderEntity,
)

from utils import (
    get_sg_entity_parent_field,
    get_sg_statuses,
    get_sg_tags,
    get_sg_custom_attributes_data
)
from constants import (
    CUST_FIELD_CODE_ID,  # Shotgrid Field for the Ayon ID.
    SHOTGRID_ID_ATTRIB,  # Ayon Entity Attribute.
    SHOTGRID_TYPE_ATTRIB,  # Ayon Entity Attribute.
)

from utils import get_logger


log = get_logger(__file__)


def create_sg_entity_from_ayon_event(
    ayon_event: Dict,
    sg_session: shotgun_api3.Shotgun,
    ayon_entity_hub: ayon_api.entity_hub.EntityHub,
    sg_project: Dict,
    sg_enabled_entities: List[str],
    custom_attribs_map: Dict[str, str],
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
    ay_id = ayon_event["summary"]["entityId"]
    ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
        ay_id, ["folder", "task"])

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
        else:
            sg_type = ay_entity.folder_type

    sg_entity = None

    if sg_id and sg_type:
        sg_entity = sg_session.find_one(sg_type, [["id", "is", int(sg_id)]])

    if sg_entity:
        log.warning(f"Entity {sg_entity} already exists in Shotgrid!")
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

        if (
            not isinstance(ay_entity, TaskEntity)
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

        log.info(f"Created Shotgrid entity: {sg_entity}")

        ay_entity.attribs.set(
            SHOTGRID_ID_ATTRIB,
            sg_entity["id"]
        )
        ay_entity.attribs.set(
            SHOTGRID_TYPE_ATTRIB,
            sg_entity["type"]
        )
        ayon_entity_hub.commit_changes()
    except Exception:
        log.error(
            f"Unable to create {sg_type} <{ay_id}> in Shotgrid!",
            exc_info=True
        )


def update_sg_entity_from_ayon_event(
    ayon_event: Dict,
    sg_session: shotgun_api3.Shotgun,
    ayon_entity_hub: ayon_api.entity_hub.EntityHub,
    custom_attribs_map: Dict[str, str],
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
            for sg_status_code, sg_status_name in sg_statuses.items():
                if new_attribs.lower() == sg_status_name.lower():
                    new_attribs = {"status": sg_status_code}
                    break
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
    ay_entity_path = ayon_event["payload"]["entityData"].get("path")
    log.debug(f"Removing Shotgrid entity: {ayon_event['payload']}")

    if not ay_entity_path:
        log.warning(
            f"Entity '{ay_id}' does not have a path to remove from Shotgrid."
        )
        return

    sg_id = ayon_event["payload"]["entityData"]["attrib"].get("shotgridId")

    if not sg_id:
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
            f"Unable to find Ayon entity with id '{ay_id}' in Shotgrid.")
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


def _create_sg_entity(
    sg_session: shotgun_api3.Shotgun,
    ay_entity: Union[TaskEntity, FolderEntity],
    sg_project: Dict,
    sg_type: str,
    sg_enabled_entities: List[str],
    custom_attribs_map: Dict[str, str],
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

    special_folder_types =["AssetCategory", "ShotCategory", "SequenceCategory"]
    # parent special folder like AssetCategory should not be created in
    # Shotgrid it is only used for grouping Asset types
    is_parent_project_entity = isinstance(ay_entity.parent, ProjectEntity)
    if (
        is_parent_project_entity
        and ay_entity.folder_type in special_folder_types
    ):
        return
    elif (not is_parent_project_entity and
          ay_entity.parent.folder_type in special_folder_types):
        sg_parent_id = None
        sg_parent_type = ay_entity.parent.folder_type
    else:
        sg_parent_id = ay_entity.parent.attribs.get(SHOTGRID_ID_ATTRIB)
        sg_parent_type = ay_entity.parent.attribs.get(SHOTGRID_TYPE_ATTRIB)

        if not sg_parent_id or not sg_parent_type:
            raise ValueError(
                    "Parent does not exist in Shotgrid!"
                    f"{sg_parent_type} <{sg_parent_id}>"
                )

    if ay_entity.entity_type == "task" and sg_parent_type != "AssetCategory":
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

    elif (
            ay_entity.entity_type == "task"
            and sg_parent_type == "AssetCategory"
            or ay_entity.entity_type != "task"
            and ay_entity.folder_type == "AssetCategory"
    ):
        # AssetCategory should not be created in Shotgrid
        # task should not be child of AssetCategory
        return
    elif ay_entity.entity_type == "task":
        data = {
            "project": sg_project,
            "entity": {"type": sg_parent_type, "id": int(sg_parent_id)},
            sg_field_name: ay_entity.label,
            CUST_FIELD_CODE_ID: ay_entity.id,
            "step": sg_step
        }
    elif ay_entity.folder_type == "Asset":
        parent_entity = ay_entity.parent
        asset_type = None
        if parent_entity.folder_type == "AssetCategory":
            parent_entity_name = parent_entity.name
            asset_type = parent_entity_name.capitalize()

        data = {
            "project": sg_project,
            "sg_asset_type": asset_type,
            sg_field_name: ay_entity.name,
            CUST_FIELD_CODE_ID: ay_entity.id,
        }
    else:
        data = {
            "project": sg_project,
            sg_field_name: ay_entity.name,
            CUST_FIELD_CODE_ID: ay_entity.id,
        }
        if isinstance(sg_parent_id, int):
            data[parent_field] = {
                "type": sg_parent_type,
                "id": int(sg_parent_id)
            }

    # Fill up data with any extra attributes from Ayon we want to sync to SG
    data.update(get_sg_custom_attributes_data(
        sg_session,
        ay_entity.attribs.to_dict(),
        sg_type,
        custom_attribs_map
    ))

    try:
        return sg_session.create(sg_type, data)
    except Exception as e:
        log.error(
            f"Unable to create SG entity {sg_type} with data: {data}")
        raise e
