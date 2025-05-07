import collections
import shotgun_api3
from typing import Dict, List, Union, Any

import ayon_api
from ayon_api.entity_hub import (
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
    get_sg_entity_as_ay_dict,
    get_sg_custom_attributes_data,
    create_new_sg_entity,
    upload_ay_reviewable_to_sg,
    get_sg_statuses,
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
    entity_hub.fetch_hierarchy_entities()

    log.info("Getting Shotgrid entities.")
    sg_ay_dicts, sg_ay_dicts_parents = get_sg_entities(
        sg_session,
        sg_project,
        sg_enabled_entities,
        project_code_field,
        custom_attribs_map,
        addon_settings=addon_settings,
    )
    compatibility_settings = addon_settings.get("compatibility_settings", {})
    default_task_type = compatibility_settings.get("default_task_type")

    ay_entity_deck = collections.deque()

    # Append the AYON project's direct children into processing queue
    for ay_entity_child in entity_hub._entities_by_parent_id[
            entity_hub.project_name]:
        ay_entity_deck.append((
            get_sg_entity_as_ay_dict(
                sg_session,
                "Project",
                sg_project["id"],
                project_code_field,
                default_task_type,
                custom_attribs_map=custom_attribs_map
            ),
            ay_entity_child
        ))
    versions = ayon_api.get_versions(entity_hub.project_name)
    for version in versions:
        product_entity = entity_hub.get_product_by_id(version["productId"])
        ay_entity_deck.append(
            (product_entity.parent,
             entity_hub.get_version_by_id(version["id"]))
        )

    ay_project_sync_status = "Synced"
    processed_ids = set()

    ay_statuses = {
        status.name: status.short_name
        for status in  entity_hub.project_entity.statuses
    }
    all_sg_statuses = {}

    while ay_entity_deck:
        (sg_ay_parent_entity, ay_entity) = ay_entity_deck.popleft()
        log.debug(f"Processing entity: '{ay_entity}'")

        sg_ay_dict = None

        # Skip entities that are not tasks or folders
        if ay_entity.entity_type not in ["task", "folder", "version"]:
            log.warning(
                f"Entity '{ay_entity.name}' is not a task, folder or version, "
                f"skipping..."
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

            attrib_values = {}
            if sg_entity_type in all_sg_statuses:
                sg_statuses = all_sg_statuses[sg_entity_type]
            else:
                sg_statuses = get_sg_statuses(sg_session, sg_entity_type)
                all_sg_statuses[sg_entity_type] = sg_statuses.copy()

            short_name = ay_statuses.get(ay_entity.status)
            if short_name in sg_statuses:
                attrib_values["status"] = short_name

            attrib_values.update(ay_entity.attribs.to_dict())

            data_to_update = get_sg_custom_attributes_data(
                sg_session,
                attrib_values,
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
                    int(sg_ay_parent_entity["attribs"][SHOTGRID_ID_ATTRIB])
                ]]
            )

            sg_ay_dict = create_new_sg_entity(
                ay_entity,
                sg_session,
                sg_project,
                sg_parent_entity,
                sg_enabled_entities,
                project_code_field,
                custom_attribs_map,
                addon_settings,
                entity_hub.project_name
            )

            if not sg_ay_dict:
                log.warning(f"AYON entity {ay_entity} not found in SG, "
                            "couldn't be created.")
                continue

            sg_entity_id = sg_ay_dict["attribs"][SHOTGRID_ID_ATTRIB]
            sg_ay_dicts[sg_entity_id] = sg_ay_dict
            sg_ay_dicts_parents[sg_parent_entity["id"]].add(sg_entity_id)

            # add new Shotgrid ID and type to existing AYON entity
            ay_entity.attribs.set(
                SHOTGRID_ID_ATTRIB,
                sg_entity_id
            )
            ay_entity.attribs.set(
                SHOTGRID_TYPE_ATTRIB,
                sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB]
            )

            if ay_entity.entity_type == "version":
                upload_ay_reviewable_to_sg(
                    sg_session,
                    entity_hub,
                    ay_entity.id,
                )


        if not sg_ay_dict:
            log.warning(f"AYON entity {ay_entity} not found in SG, ignoring it")
            continue

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
