import collections
import shotgun_api3
from typing import Dict, List, Union, Any

import ayon_api
from ayon_api.entity_hub import (
    ProjectEntity,
    TaskEntity,
    FolderEntity,
)

from constants import (
    CUST_FIELD_CODE_ID,
    CUST_FIELD_CODE_SYNC,
    SHOTGRID_ID_ATTRIB,
    SHOTGRID_TYPE_ATTRIB,
)

from utils import (
    get_sg_entities,
    get_sg_entity_parent_field,
    get_sg_entity_as_ay_dict,
    get_sg_custom_attributes_data
)

from utils import get_logger


log = get_logger(__file__)


def match_ayon_hierarchy_in_shotgrid(
    entity_hub: ayon_api.entity_hub.EntityHub,
    sg_project: Dict,
    sg_session: shotgun_api3.Shotgun,
    sg_enabled_entities: List[str],
    project_code_field: str,
    custom_attribs_map: Dict[str, str],
    addon_settings: Dict[str, Any],
):
    """Replicate an AYON project into Shotgrid.

    This function creates a "deck" which we keep increasing while traversing
    the AYON project and finding new children, this is more efficient than
    creating a dictionary with the whole AYON project structure since we
    `popleft` the elements when processing them.

    Args:
        entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        sg_project (dict): The Shotgrid project.
        sg_session (shotgun_api3.Shotgun): The Shotgrid session.
        project_code_field (str): The Shotgrid project code field.
        sg_enabled_entities (list): List of Shotgrid entities to be enabled.
        custom_attribs_map (dict): Dictionary of extra attributes to
            store in the SG entity.
        addon_settings (dict): The addon settings.
    """
    log.info("Getting AYON entities.")
    entity_hub.query_entities_from_server()

    log.info("Getting Shotgrid entities.")
    sg_ay_dicts, sg_ay_dicts_parents = get_sg_entities(
        sg_session,
        sg_project,
        sg_enabled_entities,
        project_code_field,
        custom_attribs_map,
        addon_settings=addon_settings,
    )

    ay_entity_deck = collections.deque()

    # Append the AYON project's direct children into processing queue
    for ay_entity_child in entity_hub._entities_by_parent_id[
            entity_hub.project_name]:
        ay_entity_deck.append((
            get_sg_entity_as_ay_dict(
                sg_session, "Project", sg_project["id"], project_code_field,
                custom_attribs_map=custom_attribs_map
            ),
            ay_entity_child
        ))

    ay_project_sync_status = "Synced"
    processed_ids = set()
    while ay_entity_deck:
        (sg_ay_parent_entity, ay_entity) = ay_entity_deck.popleft()
        log.debug(f"Processing entity: '{ay_entity}'")

        sg_ay_dict = None

        # Skip entities that are not tasks or folders
        if ay_entity.entity_type not in ["task", "folder"]:
            log.warning(
                f"Entity '{ay_entity.name}' is not a task or folder, skipping..."
            )
            # even the folder is not synced, we need to process its children
            _add_items_to_queue(
                entity_hub, ay_entity_deck, ay_entity, sg_ay_parent_entity
            )
            continue

        # only sync folders with type in sg_enabled_entities and tasks
        if (
            ay_entity.entity_type == "folder"
            and ay_entity.folder_type not in sg_enabled_entities
        ):
            log.warning(
                f"Entity '{ay_entity.name}' is not enabled in "
                "Shotgrid, skipping..."
            )
            # even the folder is not synced, we need to process its children
            _add_items_to_queue(
                entity_hub, ay_entity_deck, ay_entity, sg_ay_parent_entity
            )
            continue

        sg_entity_id = ay_entity.attribs.get(SHOTGRID_ID_ATTRIB, None)
        sg_entity_type = ay_entity.attribs.get(SHOTGRID_TYPE_ATTRIB, "")

        if sg_entity_id and sg_entity_id == "removed":
            # if SG entity is removed then it is marked as "removed"
            log.info(
                f"Entity '{ay_entity.name}' was removed from "
                "ShotGrid, skipping..."
            )
            continue
        elif sg_entity_id:
            sg_entity_id = int(sg_entity_id)

        if sg_entity_type == "AssetCategory":
            log.warning(
                f"Entity '{ay_entity.name}' is an AssetCategory, skipping..."
            )
            # even the folder is not synced, we need to process its children
            _add_items_to_queue(
                entity_hub, ay_entity_deck, ay_entity, sg_ay_parent_entity
            )
            continue

        # make sure we don't process the same entity twice
        if sg_entity_id in processed_ids:
            msg = (
                f"Entity {sg_entity_id} already processed, skipping..."
                f"Sg Ay Dict: {sg_ay_dict} - "
                f"SG Ay Parent Entity: {sg_ay_parent_entity}"
            )
            log.warning(msg)
            continue

        # entity was already synced before and we need to update it
        if sg_entity_id and sg_entity_id in sg_ay_dicts:
            sg_ay_dict = sg_ay_dicts[sg_entity_id]
            log.info(
                f"Entity already exists in Shotgrid {sg_ay_dict['name']}")

            if sg_ay_dict["data"][CUST_FIELD_CODE_ID] != ay_entity.id:
                # QUESTION: Can this situation even occur?
                log.warning(
                    "Shotgrid record for AYON id does not match..."
                    f"SG: {sg_ay_dict['data'][CUST_FIELD_CODE_ID]} - "
                    f"AYON: {ay_entity.id}"
                )
                try:
                    log.info("Updating SG entity with AYON id...")
                    sg_session.update(
                        sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB],
                        sg_ay_dict["attribs"][SHOTGRID_ID_ATTRIB],
                        {
                            CUST_FIELD_CODE_ID: ay_entity.id,
                            CUST_FIELD_CODE_SYNC: "Synced",
                        },
                    )
                except Exception:
                    log.error(
                        f"Unable to update SG entity {sg_ay_dict['name']}",
                        exc_info=True
                    )
                    ay_project_sync_status = "Failed"

            # Update SG entity custom attributes with AYON data
            data_to_update = get_sg_custom_attributes_data(
                sg_session,
                ay_entity.attribs.to_dict(),
                sg_entity_type,
                custom_attribs_map
            )
            if data_to_update:
                log.info("Syncing custom attributes on entity.")
                sg_session.update(
                    sg_entity_type,
                    sg_entity_id,
                    data_to_update
                )

        # entity was not synced before and need to be created
        if not sg_entity_id or not sg_ay_dict:
            sg_parent_entity = sg_session.find_one(
                sg_ay_parent_entity["attribs"][SHOTGRID_TYPE_ATTRIB],
                filters=[[
                    "id",
                    "is",
                    sg_ay_parent_entity["attribs"][SHOTGRID_ID_ATTRIB]
                ]]
            )
            sg_ay_dict = _create_new_entity(
                ay_entity,
                sg_session,
                sg_project,
                sg_parent_entity,
                sg_enabled_entities,
                project_code_field,
                custom_attribs_map,
            )
            sg_entity_id = sg_ay_dict["attribs"][SHOTGRID_ID_ATTRIB]
            sg_ay_dicts[sg_entity_id] = sg_ay_dict
            sg_ay_dicts_parents[sg_parent_entity["id"]].add(sg_entity_id)

        # add Shotgrid ID and type to AYON entity
        ay_entity.attribs.set(
            SHOTGRID_ID_ATTRIB,
            sg_entity_id
        )

        ay_entity.attribs.set(
            SHOTGRID_TYPE_ATTRIB,
            sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB]
        )

        # add processed entity to the set for duplicity tracking
        processed_ids.add(sg_entity_id)

        _add_items_to_queue(entity_hub, ay_entity_deck, ay_entity, sg_ay_dict)

    try:
        # committing changes on project children
        entity_hub.commit_changes()
    except Exception:
        log.error("Unable to commit all entities to AYON!", exc_info=True)

    # Sync project attributes from AYON to ShotGrid
    data_to_update = {
        CUST_FIELD_CODE_ID: entity_hub.project_name,
        CUST_FIELD_CODE_SYNC: ay_project_sync_status
    }
    data_to_update |= get_sg_custom_attributes_data(
        sg_session,
        entity_hub.project_entity.attribs.to_dict(),
        "Project",
        custom_attribs_map,
    )
    sg_session.update(
        "Project",
        sg_project["id"],
        data_to_update
    )

    entity_hub.project_entity.attribs.set(
        SHOTGRID_ID_ATTRIB,
        sg_project["id"]
    )

    entity_hub.project_entity.attribs.set(
        SHOTGRID_TYPE_ATTRIB,
        "Project"
    )

    # committing changes on project entity
    entity_hub.commit_changes()


def _add_items_to_queue(
    entity_hub: ayon_api.entity_hub.EntityHub,
    ay_entity_deck: collections.deque,
    ay_entity: Union[TaskEntity, FolderEntity],
    sg_ay_dict: Dict
):
    """Helper method to add children of an entity to the processing queue.

    Args:
        entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        ay_entity_deck (collections.deque): The AYON entity deck.
        ay_entity (Union[TaskEntity, FolderEntity]): The AYON entity.
        sg_ay_dict (Dict): The Shotgrid AYON entity dictionary.
    """
    for ay_entity_child in entity_hub._entities_by_parent_id.get(
                ay_entity.id, []
            ):
        ay_entity_deck.append((sg_ay_dict, ay_entity_child))


def _create_new_entity(
    ay_entity: Union[ProjectEntity, TaskEntity, FolderEntity],
    sg_session: shotgun_api3.Shotgun,
    sg_project: Dict,
    sg_parent_entity: Dict,
    sg_enabled_entities: List[str],
    project_code_field: str,
    custom_attribs_map: Dict[str, str],
):
    """Helper method to create entities in Shotgrid.

    Args:
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
        ay_entity (dict): The AYON entity.
        sg_project (dict): The Shotgrid Project.
        sg_type (str): The Shotgrid type of the new entity.
        sg_enabled_entities (list): List of Shotgrid entities to be enabled.
        project_code_field (str): The Shotgrid project code field.
        custom_attribs_map (dict): Dictionary of extra attributes to store in the SG entity.
    """
    # Task creation
    if ay_entity.entity_type == "task":
        step_query_filters = [["code", "is", ay_entity.task_type]]

        if sg_parent_entity["type"] in ["Asset", "Shot", "Episode", "Sequence"]:
            step_query_filters.append(
                ["entity_type", "is", sg_parent_entity["type"]]
            )

        task_step = sg_session.find_one(
            "Step",
            filters=step_query_filters,
        )
        if not task_step:
            raise ValueError(
                f"Unable to create Task {ay_entity.task_type} {ay_entity}\n"
                f"-> Shotgrid is missing Pipeline Step {ay_entity.task_type}"
            )

        sg_type = "Task"
        data = {
            "project": sg_project,
            "content": ay_entity.label,
            CUST_FIELD_CODE_ID: ay_entity.id,
            CUST_FIELD_CODE_SYNC: "Synced",
            "entity": sg_parent_entity,
            "step": task_step,
        }

    # Asset creation
    elif (
        ay_entity.entity_type == "folder"
        and ay_entity.folder_type == "Asset"
    ):
        sg_type = "Asset"
        # get name form sg_parent_entity
        parent_entity_name = sg_parent_entity.get("name")

        if not parent_entity_name:
            # Try to get AssetCategory type name and use it as
            # SG asset type. If not found, use None.
            parent_entity = ay_entity.parent
            parent_entity_name = parent_entity.name
            asset_type = parent_entity_name.capitalize()
        else:
            asset_type = None

        log.debug(f"Creating Asset '{ay_entity.name}' of type '{asset_type}'")
        data = {
            "sg_asset_type": asset_type,
            "project": sg_project,
            "code": ay_entity.name,
            CUST_FIELD_CODE_ID: ay_entity.id,
            CUST_FIELD_CODE_SYNC: "Synced",
        }

    # Folder creation
    else:
        sg_parent_field = get_sg_entity_parent_field(
            sg_session, sg_project, ay_entity.folder_type, sg_enabled_entities)

        sg_type = ay_entity.folder_type
        data = {
            "project": sg_project,
            "code": ay_entity.name,
            CUST_FIELD_CODE_ID: ay_entity.id,
            CUST_FIELD_CODE_SYNC: "Synced",
        }
        # If parent field is different than project, add parent field to
        # data dictionary. Each project might have different parent fields
        # defined on each entity types. This way we secure that we are
        # always creating the entity with the correct parent field.
        if (
            sg_parent_field != "project"
            and sg_parent_entity["type"] != "Project"
        ):
            data[sg_parent_field] = sg_parent_entity

    # Fill up data with any extra attributes from AYON we want to sync to SG
    data |= get_sg_custom_attributes_data(
        sg_session,
        ay_entity.attribs.to_dict(),
        sg_type,
        custom_attribs_map
    )

    try:
        sg_entity = sg_session.create(sg_type, data)
    except Exception as e:
        log.error(
            f"Unable to create SG entity {sg_type} with data: {data}")
        raise e

    return get_sg_entity_as_ay_dict(
        sg_session,
        sg_entity["type"],
        sg_entity["id"],
        project_code_field,
        custom_attribs_map=custom_attribs_map
    )
