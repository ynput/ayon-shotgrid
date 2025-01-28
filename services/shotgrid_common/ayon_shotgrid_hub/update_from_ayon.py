"""Module that handles creation, update or removal of SG entities based on AYON events.
"""
import os
import re

import shotgun_api3
import ayon_api
from typing import Dict, List, Union
import tempfile

from ayon_api.entity_hub import (
    ProjectEntity,
    TaskEntity,
    FolderEntity,
)

from utils import (
    get_sg_entity_parent_field,
    get_sg_statuses,
    get_sg_tags,
    get_sg_custom_attributes_data,
    get_sg_user_id
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

    ay_project_name = ayon_event["project"]
    try:
        sg_entity = _create_sg_entity(
            sg_session,
            ay_entity,
            sg_project,
            sg_type,
            sg_enabled_entities,
            custom_attribs_map,
            ay_project_name
        )

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

def upload_ay_reviewable_to_sg(
    ayon_event: Dict,
    sg_session: shotgun_api3.Shotgun,
    ayon_entity_hub: ayon_api.entity_hub.EntityHub,
    custom_attribs_map: Dict[str, str],
):
    ay_version_id = ayon_event["summary"]["versionId"]

    ay_version_entity = ayon_entity_hub.get_or_query_entity_by_id(
        ay_version_id, ["version"])

    if not ay_version_entity:
        raise ValueError(
            "Event has a non existent version entity "
            f"'{ay_version_id}'"
        )

    sg_version_id = ay_version_entity.attribs.get("shotgridId")
    sg_version_type = ay_version_entity.attribs.get("shotgridType")

    if not sg_version_id:
        raise ValueError(f"Version '{ay_version_id} not yet synched to SG.")

    ay_file_id = ayon_event["summary"]["fileId"]
    ay_project_name = ayon_event["project"]

    endpoint = f"projects/{ay_project_name}/files/{ay_file_id}"

    response = ayon_api.get(endpoint)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file_path = os.path.join(
            temp_dir,
            ayon_event["summary"]["filename"]
        )
        log.debug(f'Creating temp file at: {temp_file_path}')
        with open(temp_file_path, 'w+b') as temp_file:
            temp_file.write(response.content)

        sg_session.upload(
            "Version",
            sg_version_id,
            temp_file_path,
            field_name="sg_uploaded_movie",
        )

        endpoint = (f"projects/{ay_project_name}/versions/"
                    f"{ay_version_id}/thumbnail")

        response = ayon_api.get(endpoint)
        if not response:
            log.warning(f"No thumbnail for '{ay_version_id}'.")
            return

        log.debug(f"Creating thumbnail file at: {temp_file_path}")
        temp_file_path = os.path.join(temp_dir, "thumbnail.jpg")
        with open(temp_file_path, 'w+b') as temp_file:
            temp_file.write(response.content)

        sg_session.upload_thumbnail(
            sg_version_type, sg_version_id, temp_file_path
        )

def _create_sg_entity(
    sg_session: shotgun_api3.Shotgun,
    ay_entity: Union[TaskEntity, FolderEntity],
    sg_project: Dict,
    sg_type: str,
    sg_enabled_entities: List[str],
    custom_attribs_map: Dict[str, str],
    ay_project_name: str
):
    """ Create a new Shotgrid entity.

    Args:
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
        ay_entity (dict): The AYON entity.
        sg_project (dict): The Shotgrid Project.
        sg_type (str): The Shotgrid type of the new entity.
        sg_enabled_entities (list): List of Shotgrid entities to be enabled.
        custom_attribs_map (dict): Dictionary of extra attributes to store in the SG entity.
        ay_project_name (str): AYON project name, could be different from SG
            project name
    """
    sg_field_name = "code"

    special_folder_types = ["AssetCategory"]
    is_entity_special_folder_type = (
        hasattr(ay_entity, "folder_type") and
        ay_entity.parent.folder_type in special_folder_types
    )
    # parent special folder like AssetCategory should not be created in
    # Shotgrid it is only used for grouping Asset types
    is_parent_project_entity = isinstance(ay_entity.parent, ProjectEntity)

    if is_entity_special_folder_type:
        if is_parent_project_entity:
            return
        else:
            sg_parent_id = None
            sg_parent_type = ay_entity.parent.folder_type
    elif sg_type == "Version":
        # this query shouldnt be necessary as we are reaching for attribs of
        # grandparent, but it seems that field is not returned correctly TODO
        folder_id = ay_entity.parent.parent.id
        ayon_asset = ayon_api.get_folder_by_id(
            ay_project_name, folder_id)

        if not ayon_asset:
            raise ValueError(f"Not fount '{folder_id}'")

        sg_parent_id = ayon_asset["attrib"].get(SHOTGRID_ID_ATTRIB)
        sg_parent_type = ayon_asset["attrib"].get(SHOTGRID_TYPE_ATTRIB)
    else:
        sg_parent_id = ay_entity.parent.attribs.get(SHOTGRID_ID_ATTRIB)
        sg_parent_type = ay_entity.parent.attribs.get(SHOTGRID_TYPE_ATTRIB)

        if not sg_parent_id or not sg_parent_type:
            raise ValueError(
                    "Parent does not exist in Shotgrid!"
                    f"{sg_parent_type} <{sg_parent_id}>"
                )

    parent_field = get_sg_entity_parent_field(
        sg_session,
        sg_project,
        sg_type,
        sg_enabled_entities
    )

    sg_parent = None
    if sg_parent_id:
        sg_parent = {"type": sg_parent_type, "id": int(sg_parent_id)}

    data = None
    if parent_field.lower() == "project":
        data = {
            "project": sg_project,
            sg_field_name: ay_entity.name,
            CUST_FIELD_CODE_ID: ay_entity.id,
        }
    elif ay_entity.entity_type == "folder":
        data = {
            "project": sg_project,
            sg_field_name: ay_entity.name,
            CUST_FIELD_CODE_ID: ay_entity.id,
            parent_field: sg_parent
        }

        parent_entity = ay_entity.parent
        if parent_entity.folder_type == "AssetCategory":
            parent_entity_name = parent_entity.name
            asset_type = parent_entity_name.capitalize()
            data["sg_asset_type"] = asset_type
    elif ay_entity.entity_type == "task":
        # AssetCategory should not be created in Shotgrid
        if ay_entity.folder_type == "AssetCategory":
            return

        sg_field_name = "content"
        sg_step = _get_step(sg_session, ay_entity, sg_parent_type)
        data = {
            "project": sg_project,
            parent_field: sg_parent,
            sg_field_name: ay_entity.label,
            CUST_FIELD_CODE_ID: ay_entity.id,
            "step": sg_step
        }
    elif ay_entity.entity_type == "version":
        sg_user_id = get_sg_user_id(
            "petr.kalis_ynput.io")  # ayon_event["user"]

        product_name = ay_entity.parent.name
        version_str = str(ay_entity.version).zfill(3)
        version_name = f"{product_name}_v{version_str}"
        data = {
            "project": sg_project,
            parent_field: sg_parent,
            sg_field_name: version_name,
            "user": {'type': 'HumanUser', 'id': sg_user_id},
        }

        _add_paths(ay_project_name, ay_entity, data)

    if not data:
        return

    # Fill up data with any extra attributes from AYON we want to sync to SG
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


def _add_paths(ay_project_name: str, ay_entity: Dict, data_to_update: Dict):
    """Adds local path to review file to `sg_path_to_*` as metadata.

     We are storing local paths for external processing, some studios might
     have tools to handle review files in another processes.
     """
    thumbnail_path = None
    found_reviewable = False

    representations = ayon_api.get_representations(
        ay_project_name, version_ids=[ay_entity.id])

    ay_version = ayon_api.get_version_by_id(ay_project_name, ay_entity.id)

    for representation in representations:

        local_path = representation["attrib"]["path"]
        representation_name = representation["name"]

        if representation_name == "thumbnail":
            thumbnail_path = local_path
            continue

        if not representation_name.startswith("review"):
            continue

        found_reviewable = True
        has_slate = "slate" in ay_version["attrib"]["families"]
        # clunky guess, not having access to ayon_core.VIDEO_EXTENSIONS
        if len(representation["files"]) == 1:
            data_to_update["sg_path_to_movie"] = local_path
            if has_slate:
                data_to_update["sg_movie_has_slate"] = True
        else:
            # Replace the frame number with '%04d'
            path_to_frame = re.sub(r"\.\d+\.", ".%04d.", local_path)

            data_to_update.update({
                "sg_path_to_movie": path_to_frame,
                "sg_path_to_frames": path_to_frame,
            })

            if has_slate:
                data_to_update["sg_frames_have_slate"] = True

    if not found_reviewable and thumbnail_path:
        data_to_update.update({
            "sg_path_to_movie": thumbnail_path,
            "sg_path_to_frames": thumbnail_path,
        })

def _get_step(sg_session, ay_entity, sg_parent_type):
    sg_step = None
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
    return sg_step
