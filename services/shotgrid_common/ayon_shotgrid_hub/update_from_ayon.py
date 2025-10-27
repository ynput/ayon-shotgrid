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
        return ay_entity

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
            return None

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
        return ay_entity

    except Exception:
        log.error(
            f"Unable to create {sg_type} <{ay_id}> in Shotgrid!",
            exc_info=True
        )
        return None


def sync_sg_playlist_from_ayon_event(
    ayon_event: Dict,
    sg_session: shotgun_api3.Shotgun,
    ayon_entity_hub: ayon_api.entity_hub.EntityHub,
    sg_project: Dict
):
    log.debug(f"{ayon_event = }")
    # check if it's a list of versions
    # lists of folders/tasks are not supported by SG
    list_type = ayon_event["summary"].get("entity_type")
    if not list_type == "version":
        log.info("Only EntityLists of type 'version' are supported.")
        return

    # get all versions in the list
    # and their corresponding SG IDs
    entity_list = None
    try: # gotta try here since on delete the EntityList doesn't exist anymore
        # get_entity_list() doesn't return the linked versions, so i use the rest variant here
        entity_list = ayon_api.get_entity_list_rest(
            project_name=sg_project["name"],
            list_id=ayon_event["summary"]["id"],
        )
    except Exception:
        log.debug("EntityList couldn't be fetched. We're probably deleting the list.")

    if entity_list:
        version_ids = [entity["entityId"] for entity in entity_list["items"]]
        log.debug(f"{entity_list = }")
        log.debug(f"{version_ids = }")
        ay_versions = ayon_api.get_versions(
            project_name=sg_project["name"],
            version_ids=version_ids,
            fields=["attrib.shotgridId"]
        )
        sg_versions = []
        for version in ay_versions:
            log.debug(f"{version = }")
            sg_id = version["attrib"].get("shotgridId")
            if sg_id:
                sg_versions.append({"type": "Version", "id": int(sg_id)})
        log.debug(f"{sg_versions = }")

    match ayon_event["topic"]:
        case "entity_list.created":
            log.info(f"Creating new SG Playlist from AYON EntityList {entity_list['label']}")
            playlist = sg_session.create(
                "Playlist",
                {
                    "project": {
                        "type": "Project",
                        "id": sg_project["id"]
                    },
                    "code": ayon_event["summary"]["label"],
                    "versions": sg_versions,  # link versions to sg playlist
                    "sg_ayon_id": entity_list["id"],
                }
            )
            log.debug(f"{playlist = }")

            # save back sg id on ayon entity list
            # this will trigger the update event next!
            ayon_api.raw_patch(
                f"/projects/{sg_project['name']}/lists/{entity_list['id']}",
                json={
                    "attrib": {"sg_id": playlist["id"]}
                }
            )
        case "entity_list.changed":
            if not entity_list["attrib"].get("sg_id"):
                log.error("SG Playlist ID not found on AYON EntityList")

            list_sg_id = entity_list["attrib"]["sg_id"]
            log.info(f"Updating SG Playlist {list_sg_id}")
            sg_session.update(
                "Playlist",
                int(list_sg_id),
                {
                    "versions": sg_versions,
                    "locked": not entity_list.get("active", True),
                }
            )
        case "entity_list.deleted":
            ayon_list_id = ayon_event["summary"]["id"]
            sg_playlist = sg_session.find_one(
                "Playlist",
                filters=[["sg_ayon_id", "is", ayon_list_id]]
            )
            if not sg_playlist:
                log.error(
                    f"Could not find SG Playlist for AYON EntityList ID "
                    f"{ayon_list_id}"
                )
                return

            log.info(f"Deleting SG Playlist {sg_playlist['id']}")
            sg_session.delete(
                "Playlist",
                int(sg_playlist["id"])
            )


def _get_parent_sg_id_type(ay_entity):
    """ Recursively find a parent with a valid Shotgrid ID.
    """
    # Sync new Asset parented under an AssetCategory.
    # Sync children of a generic Folder.
    sg_parent_id = ay_entity.parent.attribs.get(SHOTGRID_ID_ATTRIB)
    sg_parent_type = ay_entity.parent.attribs.get(SHOTGRID_TYPE_ATTRIB)

    if sg_parent_id and sg_parent_type:
        return sg_parent_id, sg_parent_type

    elif not ay_entity.parent:
        return None, None

    return _get_parent_sg_id_type(ay_entity.parent)


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
            raise ValueError(
                f"Could not find Version parent folder from ID: '{folder_id}'."
            )

        sg_parent_id = ayon_asset["attrib"].get(SHOTGRID_ID_ATTRIB)
        sg_parent_type = ayon_asset["attrib"].get(SHOTGRID_TYPE_ATTRIB)
    else:
        sg_parent_id, sg_parent_type = _get_parent_sg_id_type(ay_entity)

    if not sg_parent_id or not sg_parent_type:
        raise ValueError(f"Could not find valid parent for {ay_entity}.")

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
    sg_project: Dict,
    sg_enabled_entities: List[str],
    sg_project_code_field: [str],
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
        ay_id, ["folder", "task", "version"])

    if not ay_entity:
        raise ValueError(
            "Event has a non existent entity? "
            f"{ayon_event['summary']['entityId']}"
        )

    sg_id = ay_entity.attribs.get("shotgridId")
    sg_entity_type = ay_entity.attribs.get("shotgridType")

    # react to an AYON entity being updated
    # that does not exist yet in Shotgrid.
    if sg_id is None:

        # Create SG entity and update existing ay_entity.
        ay_entity = create_sg_entity_from_ayon_event(
            ayon_event,
            sg_session,
            ayon_entity_hub,
            sg_project,
            sg_enabled_entities,
            sg_project_code_field,
            custom_attribs_map,
            addon_settings,
        )

        sg_id = ay_entity.attribs.get("shotgridId")
        sg_entity_type = ay_entity.attribs.get("shotgridType")

        if sg_id is None:
            log.warning(f"Could not create SG entity from {ay_entity}.")
            return

    try:
        sg_field_name = "code"
        if ay_entity["entity_type"] == "task":
            sg_field_name = "content"

        data_to_update = {
            CUST_FIELD_CODE_ID: ay_entity["id"]
        }

        try:
            data_to_update[sg_field_name] = ay_entity["name"]
        except NotImplementedError:
            pass  # Version does not have a name.

        # Add any possible new values to update
        new_attribs = ayon_event["payload"].get("newValue")

        if isinstance(new_attribs, dict):
            # If payload newValue is a dict it means it's an attribute update
            # but this only apply to case were attribs key is in the
            # newValue dict
            if "attribs" in new_attribs:
                new_attribs = new_attribs["attribs"]

        # Label changed
        elif ayon_event["topic"].endswith("label_changed"):
            new_value = ayon_event["payload"].get("newValue")
            data_to_update[sg_field_name] = new_value
            new_attribs = None

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

