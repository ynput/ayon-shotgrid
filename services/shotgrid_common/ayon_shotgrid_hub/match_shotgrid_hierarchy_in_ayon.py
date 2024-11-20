import collections
import random
import shotgun_api3
from typing import Dict, List

import ayon_api

from ayon_api import slugify_string

from constants import (
    CUST_FIELD_CODE_ID,
    CUST_FIELD_CODE_SYNC,
    SHOTGRID_ID_ATTRIB,
    SHOTGRID_TYPE_ATTRIB,
)

from ayon_api.entity_hub import ProjectEntity

from utils import (
    create_new_ayon_entity,
    get_sg_entities,
    get_asset_category,
    get_sequence_category,
    get_shot_category,
    update_ay_entity_custom_attributes,
)

from utils import get_logger


log = get_logger(__file__)


def match_shotgrid_hierarchy_in_ayon(
    entity_hub: ayon_api.entity_hub.EntityHub,
    sg_project: Dict,
    sg_session: shotgun_api3.Shotgun,
    sg_enabled_entities: List[str],
    project_code_field: str,
    custom_attribs_map: Dict[str, str],
    addon_settings: Dict[str, str]
):
    """Replicate a Shotgrid project into AYON.

    This function creates a "deck" which we keep increasing while traversing
    the Shotgrid project and finding new children, this is more efficient than
    creating a dictionary with the while Shotgrid project structure since we
    `popleft` the elements when processing them.

    Args:
        entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        sg_project (dict): The Shotgrid project.
        sg_project (shotgun_api3.Shotgun): The Shotgrid session.
        project_code_field (str): The Shotgrid project code field.
    """
    log.info("Getting Shotgrid entities.")
    sg_ay_dicts, sg_ay_dicts_parents = get_sg_entities(
        sg_session,
        sg_project,
        sg_enabled_entities,
        project_code_field,
        custom_attribs_map,
    )

    sg_ay_dicts_deck = collections.deque()

    # Append the project's direct children.
    for sg_ay_dict_child_id in sg_ay_dicts_parents[sg_project["id"]]:
        sg_ay_dicts_deck.append(
            (entity_hub.project_entity, sg_ay_dict_child_id)
        )

    sg_project_sync_status = "Synced"
    processed_ids = set()

    while sg_ay_dicts_deck:
        (ay_parent_entity, sg_ay_dict_child_id) = sg_ay_dicts_deck.popleft()
        sg_ay_dict = sg_ay_dicts[sg_ay_dict_child_id]
        sg_entity_id = sg_ay_dict["attribs"][SHOTGRID_ID_ATTRIB]
        if sg_entity_id in processed_ids:
            msg = (
                f"Entity {sg_entity_id} already processed, skipping..."
                f"Sg Ay Dict: {sg_ay_dict} - "
                f"Ay Parent Entity: {ay_parent_entity}"
            )
            log.warning(msg)
            continue

        processed_ids.add(sg_entity_id)

        log.debug(f"Deck size: {len(sg_ay_dicts_deck)}")

        ay_entity = None
        sg_entity_sync_status = "Synced"

        ay_id = sg_ay_dict["data"].get(CUST_FIELD_CODE_ID)
        if ay_id:
            ay_entity = entity_hub.get_or_query_entity_by_id(
                ay_id, [sg_ay_dict["type"]])

        # If we haven't found the ay_entity by its id, check by its name
        # to avoid creating duplicates and erroring out
        if ay_entity is None:
            shotgrid_type = sg_ay_dict["attribs"].get(SHOTGRID_TYPE_ATTRIB)
            if shotgrid_type == "AssetCategory":
                ay_parent_entity = get_asset_category(
                    entity_hub,
                    ay_parent_entity,
                    sg_ay_dict,
                    addon_settings
                )
                # If the entity has children, add it to the deck
                for sg_child_id in sg_ay_dicts_parents.get(sg_entity_id, []):
                    sg_ay_dicts_deck.append((ay_parent_entity, sg_child_id))
                continue

            elif shotgrid_type == "Sequence":
                ay_parent_entity = get_sequence_category(
                    entity_hub,
                    ay_parent_entity,
                    sg_ay_dict,
                    addon_settings
                )

            elif shotgrid_type == "Shot":
                ay_parent_entity = get_shot_category(
                    entity_hub,
                    ay_parent_entity,
                    sg_ay_dict,
                    addon_settings
                )

            name = slugify_string(sg_ay_dict["name"])
            for child in ay_parent_entity.children:
                if child.name.lower() == name.lower():
                    ay_entity = child
                    break

        # If we couldn't find it we create it.
        if ay_entity is None:
            if not ay_entity:
                ay_entity = create_new_ayon_entity(
                    sg_session,
                    entity_hub,
                    ay_parent_entity,
                    sg_ay_dict
                )
        else:
            ay_sg_id_attrib = ay_entity.attribs.get(
                SHOTGRID_ID_ATTRIB
            )

            # If the ShotGrid ID in AYON doesn't match the one in ShotGrid
            if str(ay_sg_id_attrib) != str(sg_entity_id):  # noqa
                log.error(
                    f"The AYON entity {ay_entity.name} <{ay_entity.id}> has the "  # noqa
                    f"ShotgridId {ay_sg_id_attrib}, while the ShotGrid ID "  # noqa
                    f"should be {sg_entity_id}"
                )
                sg_entity_sync_status = "Failed"
                sg_project_sync_status = "Failed"
            else:
                update_ay_entity_custom_attributes(
                    ay_entity, sg_ay_dict, custom_attribs_map
                )

        # skip if no ay_entity is found
        # perhaps due Task with project entity as parent
        if not ay_entity:
            log.error(f"Entity {sg_ay_dict} not found in AYON.")
            continue

        # Update SG entity with new created data
        sg_ay_dict["data"][CUST_FIELD_CODE_ID] = ay_entity.id
        sg_ay_dicts[sg_entity_id] = sg_ay_dict

        # If the entity is not a "Folder" or "AssetCategory" we update the
        # entity ID and sync status in Shotgrid and AYON
        if (
            sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB] not in [
                "Folder", "AssetCategory"
            ]
            and (
                sg_ay_dict["data"][CUST_FIELD_CODE_ID] != ay_entity.id
                or sg_ay_dict["data"][CUST_FIELD_CODE_SYNC] != sg_entity_sync_status  # noqa
            )
        ):
            log.debug(
                "Updating AYON entity ID and sync status in SG and AYON")
            update_data = {
                CUST_FIELD_CODE_ID: ay_entity.id,
                CUST_FIELD_CODE_SYNC: sg_entity_sync_status
            }
            # Update Shotgrid entity with AYON ID and sync status
            sg_session.update(
                sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB],
                sg_entity_id,
                update_data
            )
            ay_entity.data.update(update_data)

        # If the entity has children, add it to the deck
        for sg_child_id in sg_ay_dicts_parents.get(sg_entity_id, []):
            sg_ay_dicts_deck.append((ay_parent_entity, sg_child_id))

    # Sync project attributes from Shotgrid to AYON
    entity_hub.project_entity.attribs.set(
        SHOTGRID_ID_ATTRIB,
        sg_project["id"]
    )
    entity_hub.project_entity.attribs.set(
        SHOTGRID_TYPE_ATTRIB,
        "Project"
    )
    for ay_attrib, sg_attrib in custom_attribs_map.items():
        attrib_value = sg_project.get(sg_attrib) \
            or sg_project.get(f"sg_{sg_attrib}")

        if attrib_value is None:
            continue

        if ay_attrib == "tags":
            project_name = entity_hub.project_entity.project_name
            _add_tags(project_name, attrib_value)
            continue

        entity_hub.project_entity.attribs.set(
            ay_attrib,
            attrib_value
        )

    try:
        entity_hub.commit_changes()
    except Exception:
        log.error(
            "Unable to commit all entities to AYON!", exc_info=True)

    log.info(
        "Processed entities successfully!. "
        f"Amount of entities: {len(processed_ids)}"
    )

    # Update Shotgrid project with AYON ID and sync status
    sg_session.update(
        "Project",
        sg_project["id"],
        {
            CUST_FIELD_CODE_ID: entity_hub.project_entity.id,
            CUST_FIELD_CODE_SYNC: sg_project_sync_status
        }
    )


def _add_tags(project_name, tags):
    """Add tags to AYON project.

    Updates project Anatomy. No explicit way how to do it in ayon_api yet.

    Args:
        project_name (str)
        tags (list of dict):
            [{'id': 408, 'name': 'project_tag', 'type': 'Tag'}]
    """
    anatomy_data = ayon_api.get(f"projects/{project_name}/anatomy").data

    existing_tags = {tag["name"] for tag in anatomy_data["tags"]}
    update = False
    for tag in tags:
        tag_name = tag["name"]
        if tag_name not in existing_tags:
            new_tag = {
                "name": tag_name,
                "color": _create_color(),
                "original_name": tag_name
            }
            anatomy_data["tags"].append(new_tag)
            existing_tags.add(tag_name)
            update = True

    if update:
        result = ayon_api.post(
            f"projects/{project_name}/anatomy", **anatomy_data)
        if result.status_code != 204:
            raise RuntimeError("Failed to update tags")


def _create_color() -> str:
    """Return a random color visible on dark background"""
    color = [random.randint(0, 255) for _ in range(3)]
    if sum(color) < 400:
        color = [255 - x for x in color]
    return f'#{"".join([f"{x:02x}" for x in color])}'
