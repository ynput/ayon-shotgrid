import os
import json
import hashlib
import logging
import collections
from typing import Dict, Optional, Union

import ayon_api

from constants import (
    AYON_SHOTGRID_ATTRIBUTES_MAP,
    CUST_FIELD_CODE_ID,
    CUST_FIELD_CODE_SYNC,
    SG_COMMON_ENTITY_FIELDS,
    SG_PROJECT_ATTRS,
    SHOTGRID_ID_ATTRIB,
    SHOTGRID_TYPE_ATTRIB,
)

from ayon_api.entity_hub import (
    ProjectEntity,
    TaskEntity,
    FolderEntity,
)
from ayon_api.utils import slugify_string
from ayon_api import get_attributes_for_type

import shotgun_api3


_loggers = {}


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance with the given name."""
    if name in _loggers:
        return _loggers[name]

    # get environment variable DEBUG level
    log_level = os.environ.get("LOGLEVEL", "INFO").upper()

    logger = logging.Logger(name)
    _loggers[name] = logger
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(log_level)

    formatting_str = (
        "%(asctime)s.%(msecs)03d %(levelname)s: %(message)s"
    )

    if log_level == "DEBUG":
        formatting_str = (
            "%(asctime)s.%(msecs)03d | %(module)s | %(funcName)s | "
            "%(levelname)s: %(message)s"
        )

    # create formatter
    formatter = logging.Formatter(
        fmt=formatting_str,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # add formatter to ch
    ch.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(ch)

    return logger


# create logger
log = get_logger(__name__)


def get_event_hash(event_topic: str, event_id: int) -> str:
    """Create a SHA-256 hash from the event topic and event ID.

    Arguments:
        event_topic (str): The event topic.
        event_id (int): The event ID.

    Returns:
        str: The SHA-256 hash.
    """
    data = {
        "event_topic": event_topic,
        "event_id": event_id,
    }
    json_data = json.dumps(data)
    return hashlib.sha256(json_data.encode("utf-8")).hexdigest()


def _sg_to_ay_dict(
    sg_entity: dict,
    project_code_field: str,
    custom_attribs_map: dict,
) -> dict:
    """Morph a ShotGrid entity dict into an ayon-api Entity Hub compatible one.

    Create a dictionary that follows the AYON Entity Hub schema and handle edge
    cases so it's ready for AYON consumption.

    Folders: https://github.com/ynput/ayon-python-api/blob/30d702618b58676c3708f09f131a0974a92e1002/ayon_api/entity_hub.py#L2397  # noqa
    Tasks: https://github.com/ynput/ayon-python-api/blob/30d702618b58676c3708f09f131a0974a92e1002/ayon_api/entity_hub.py#L2579  # noqa

    Args:
        sg_entity (dict): Shotgun Entity dict representation.
        project_code_field (str): The ShotGrid project code field.
        custom_attribs_map (dict): Dictionary that maps names of attributes in
            AYON to ShotGrid equivalents.
    """
    ay_entity_type = "folder"
    task_type = None
    folder_type = None

    if sg_entity["type"] == "Task":
        ay_entity_type = "task"
        if not sg_entity["step"]:
            raise ValueError(
                f"Task {sg_entity} has no Pipeline Step assigned."
            )

        label = sg_entity["content"]
        task_type = sg_entity["step"]["name"]

        if not label and not task_type:
            raise ValueError(f"Unable to parse Task {sg_entity}")
        if label:
            name = slugify_string(label)
        else:
            name = slugify_string(task_type)

    elif sg_entity["type"] == "Project":
        name = slugify_string(sg_entity[project_code_field])
        label = sg_entity[project_code_field]
    else:
        name = slugify_string(sg_entity["code"])
        label = sg_entity["code"]
        folder_type = sg_entity["type"]

    sg_ay_dict = {
        "type": ay_entity_type,
        "label": label,
        "name": name,
        "attribs": {
            SHOTGRID_ID_ATTRIB: sg_entity["id"],
            SHOTGRID_TYPE_ATTRIB: sg_entity["type"],
        },
        "data": {
            # We store the ShotGrid ID and the Sync status in the data
            # dictionary so we can easily access them when needed
            # And avoid any conflicts with the AYON attributes we only set
            # sync status to "Failed" if the ID is not set
            CUST_FIELD_CODE_SYNC: (
                sg_entity.get(CUST_FIELD_CODE_SYNC)
                if sg_entity.get(CUST_FIELD_CODE_ID)
                else "Failed"
            ),
            CUST_FIELD_CODE_ID: sg_entity.get(CUST_FIELD_CODE_ID),
        }
    }
    if custom_attribs_map:
        for ay_attrib, sg_attrib in custom_attribs_map.items():
            sg_value = sg_entity.get(sg_attrib) or sg_entity.get(f"sg_{sg_attrib}")

            # If no value in SG entity skip
            if sg_value is None:
                continue

            sg_ay_dict["attribs"][ay_attrib] = sg_value

    if task_type:
        sg_ay_dict["task_type"] = task_type
    elif folder_type:
        sg_ay_dict["folder_type"] = folder_type

    return sg_ay_dict


def create_ay_fields_in_sg_entities(
    sg_session: shotgun_api3.Shotgun,
    sg_entities: list,
    custom_attribs_map: dict,
    custom_attribs_types: dict
):
    """Create AYON fields in ShotGrid entities.

    Some fields need to exist in the ShotGrid Entities, mainly the `sg_ayon_id`
    and `sg_ayon_sync_status` for the correct operation of the handlers.

    Args:
        sg_session (shotgun_api3.Shotgun): Instance of a ShotGrid API Session.
        sg_entities (list): List of ShotGrid entities to create the fields in.
        custom_attribs_map (dict): Dictionary that maps names of attributes in
            AYON to ShotGrid equivalents.
        custom_attribs_types (dict): Dictionary that contains a tuple for each
            attribute containing the type of data and the scope of the attribute.
    """
    for sg_entity_type in sg_entities:
        get_or_create_sg_field(
            sg_session,
            sg_entity_type,
            "Ayon ID",
            "text",
            CUST_FIELD_CODE_ID,
        )

        get_or_create_sg_field(
            sg_session,
            sg_entity_type,
            "Ayon Sync Status",
            "list",
            CUST_FIELD_CODE_SYNC,
            field_properties={
                "name": "Ayon Sync Status",
                "description": "The Synchronization status with AYON.",
                "valid_values": ["Synced", "Failed", "Skipped"],
            }
        )

        # Add custom attributes to entity
        create_ay_custom_attribs_in_sg_entity(
            sg_session,
            sg_entity_type,
            custom_attribs_map,
            custom_attribs_types
        )


def create_ay_custom_attribs_in_sg_entity(
    sg_session: shotgun_api3.Shotgun,
    sg_entity_type: str,
    custom_attribs_map: dict,
    custom_attribs_types: dict
):
    """Create AYON custom attributes in ShotGrid entities.

    Args:
        sg_session (shotgun_api3.Shotgun): Instance of a ShotGrid API Session.
        sg_entities (list): List of ShotGrid entities to create the fields in.
        custom_attribs_map (dict): Dictionary that maps names of attributes in
            AYON to ShotGrid equivalents.
        custom_attribs_types (dict): Dictionary that contains a tuple for each
            attribute containing the type of data and the scope of the
            attribute.
    """
    # Add all the custom attributes
    for sg_attrib in custom_attribs_map.values():

        data_scope = custom_attribs_types.get(sg_attrib)
        if not data_scope:
            continue

        data_type, ent_scope = data_scope

        # If SG entity type is not in the scope set on the attribute, skip it
        if sg_entity_type not in ent_scope:
            continue

        field_type = AYON_SHOTGRID_ATTRIBUTES_MAP[data_type]["name"]

        # First we simply validate whether the built-in attribute
        # already exists in the SG entity
        exists = check_sg_attribute_exists(
            sg_session,
            sg_entity_type,
            sg_attrib,
        )
        # If it doesn't exist, we create a custom attribute on the
        # SG entity by prefixing it with "sg_"
        if not exists:
            get_or_create_sg_field(
                sg_session,
                sg_entity_type,
                sg_attrib,
                field_type
            )


def create_ay_fields_in_sg_project(
    sg_session: shotgun_api3.Shotgun,
    custom_attribs_map: dict,
    custom_attribs_types: dict
):
    """Create AYON Project fields in ShotGrid.

    This will create Project Unique attributes into ShotGrid.

    Args:
        sg_session (shotgun_api3.Shotgun): Instance of a ShotGrid API Session.
        custom_attribs_map (dict): Dictionary that maps names of attributes in
            AYON to ShotGrid equivalents.
        custom_attribs_types (dict): Dictionary that contains a tuple for each
            attribute containing the type of data and the scope of the
            attribute.
    """
    ayon_attribs_mapping = {
        attr_name: attr_dict["type"]
        for attr_name, attr_dict in get_attributes_for_type("folder").items()
    }
    for attribute, attribute_values in SG_PROJECT_ATTRS.items():
        sg_field_name = attribute_values["name"]
        sg_field_code = attribute_values["sg_field"]
        sg_field_type = attribute_values.get("type")
        sg_field_properties = {}

        if not sg_field_type:
            sg_field_type = ayon_attribs_mapping.get(attribute)

        if sg_field_type == "checkbox":
            sg_field_properties = {"default_value": False}

        get_or_create_sg_field(
            sg_session,
            "Project",
            sg_field_name,
            sg_field_type,
            field_code=sg_field_code,
            field_properties=sg_field_properties
        )

        # Add custom attributes to project
        create_ay_custom_attribs_in_sg_entity(
            sg_session,
            "Project",
            custom_attribs_map,
            custom_attribs_types
        )


def create_sg_entities_in_ay(
    project_entity: ProjectEntity,
    sg_session: shotgun_api3.Shotgun,
    shotgrid_project: dict,
    sg_enabled_entities: list,
):
    """Ensure AYON has all the SG Steps (to use as task types) and Folder types.

    Args:
        project_entity (ProjectEntity): The ProjectEntity for a given project.
        sg_session (shotgun_api3.Shotgun): Shotgun Session object.
        shotgrid_project (dict): The project owning the Tasks.
        sg_enabled_entities (list): The enabled entities.
    """

    # Types of SG entities to ignore as AYON folders
    ignored_folder_types = {"task", "version"}

    # Find ShotGrid Entities that are to be treated as folders
    sg_folder_entities = [
        {"name": entity_type}
        for entity_type, _ in get_sg_project_enabled_entities(
            sg_session,
            shotgrid_project,
            sg_enabled_entities
        ) if entity_type.lower() not in ignored_folder_types
    ]

    new_folder_types = sg_folder_entities + project_entity.folder_types
    # So we can have a specific folder for AssetCategory
    new_folder_types.append({"name": "AssetCategory"})

    # Make sure list items are unique
    new_folder_types = list({
        entity['name']: entity
        for entity in new_folder_types
    }.values())
    project_entity.folder_types = new_folder_types

    # Add ShotGrid Statuses to AYON Project Entity
    ay_status_codes = [s.short_name.lower() for s in list(project_entity.statuses)]
    for sg_entity_type in sg_enabled_entities:
        if sg_entity_type == "Project":
            # Skipping statuses from SG project as they are irrelevant in AYON
            continue
        for status_code, status_name in get_sg_statuses(sg_session, sg_entity_type).items():
            if status_code.lower() not in ay_status_codes:
                project_entity.statuses.create(status_name, short_name=status_code)
                ay_status_codes.append(status_code)

    # Add Project task types by querying ShotGrid Pipeline steps
    sg_steps = [
        {"name": step[0], "shortName": step[1]}
        for step in get_sg_pipeline_steps(
            sg_session,
            shotgrid_project,
            sg_enabled_entities
        )
    ]
    new_task_types = sg_steps + project_entity.task_types
    new_task_types = list({
        task['name']: task
        for task in new_task_types
    }.values())
    project_entity.task_types = new_task_types

    return sg_folder_entities, sg_steps


def create_asset_category(entity_hub, parent_entity, sg_ay_dict):
    """Create an "AssetCategory" folder in AYON.

    Args:
        entity_hub (ayon_api.EntityHub): The project's entity hub.
        parent_entity: AYON parent entity.
        sg_ay_dict (dict): The ShotGrid entity ready for AYON consumption.
    """
    asset_category = sg_ay_dict["data"]["sg_asset_type"]
    # asset category entity name
    cat_ent_name = slugify_string(asset_category).lower()

    asset_category_entity = {
        "label": asset_category,
        "name": cat_ent_name,
        "attribs": {
            SHOTGRID_ID_ATTRIB: slugify_string(asset_category).lower(),
            SHOTGRID_TYPE_ATTRIB: "AssetCategory",
        },
        "parent_id": parent_entity.id,
        "data": {
            CUST_FIELD_CODE_ID: None,
            CUST_FIELD_CODE_SYNC: None,
        },
        "folder_type": "AssetCategory",
    }

    asset_category_entity = entity_hub.add_new_folder(**asset_category_entity)

    log.info(f"Created AssetCategory: {asset_category_entity}")
    return asset_category_entity


def get_asset_category(entity_hub, parent_entity, sg_ay_dict):
    """Look for existing "AssetCategory" folders in AYON.

        Asset categories are not entities per se in ShotGrid, they are
        a "string" field in the `Asset` type, which is then used to visually
        group `Asset`s; here we attempt to find any `AssetCategory` folder
        type that already matches the one in ShotGrid.

    Args:
        entity_hub (ayon_api.EntityHub): The project's entity hub.
        parent_entity: AYON parent entity.
        sg_ay_dict (dict): The ShotGrid entity ready for AYON consumption.

    """
    # just in case the asset type doesn't exist yet
    if not sg_ay_dict["data"].get("sg_asset_type"):
        sg_ay_dict["data"]["sg_asset_type"] = sg_ay_dict["name"]

    asset_category_name = slugify_string(
        sg_ay_dict["data"]["sg_asset_type"]).lower()

    asset_categories = [
        entity
        for entity in parent_entity.get_children()
        if (
            entity.entity_type == "folder"
            and entity.folder_type == "AssetCategory"
            and entity.name == asset_category_name
        )
    ]

    for asset_category in asset_categories:
        return asset_category

    try:
        return create_asset_category(entity_hub, parent_entity, sg_ay_dict)
    except Exception:
        log.error("Unable to create AssetCategory.", exc_info=True)

    return None


def get_or_create_sg_field(
    sg_session: shotgun_api3.Shotgun,
    sg_entity_type: str,
    field_name: str,
    field_type: str,
    field_code: Optional[str] = None,
    field_properties: Optional[dict] = {}
):
    """Return a field from a ShotGrid Entity or create it if it doesn't exist.

    Args:
        sg_session (shotgun_api3.Shotgun): Instance of a ShotGrid API Session.
        sg_entity_type (str): The ShotGrid entity type the field belongs to.
        field_name (str): The ShotGrid field name, displayed in the UI.
        field_type (str): The type of ShotGrid field.
        field_code (Optional[str]): The ShotGrid field code, inferred from the
            the `field_name` if not provided.
        field_properties (Optional[dict]): Some fields allow extra properties,
            these can be defined with this argument.

    Returns:
        attribute_exists (str): The Field name (code).
    """
    if not field_code:
        field_code = f"sg_{field_name.lower().replace(' ', '_')}"

    attribute_exists = check_sg_attribute_exists(
        sg_session, sg_entity_type, field_code)

    if not attribute_exists:

        try:
            attribute_exists = sg_session.schema_field_create(
                sg_entity_type,
                field_type,
                field_name,
                properties=field_properties,
            )
            return attribute_exists
        except Exception:
            log.error(
                "Can't create ShotGrid field "
                f"{sg_entity_type} > {field_code}.",
                exc_info=True
            )

    return attribute_exists


def check_sg_attribute_exists(
    sg_session: shotgun_api3.Shotgun,
    sg_entity_type: str,
    field_code: str,
    check_writable: bool = False,
) -> bool:
    """Validate whether given field code exists under that entity type"""
    try:
        schema_field = sg_session.schema_field_read(
            sg_entity_type,
            field_name=field_code
        )
        # If we are checking whether the attribute can be written to
        # we check the "editable" key in the schema field
        if check_writable:
            is_writable = schema_field[field_code].get(
                "editable", {}).get("value")
            if not is_writable:
                return False

        return schema_field
    except Exception:
        # shotgun_api3.shotgun.Fault: API schema_field_read()
        pass

    return False


def get_sg_entities(
    sg_session: shotgun_api3.Shotgun,
    sg_project: dict,
    sg_enabled_entities: list,
    project_code_field: str,
    custom_attribs_map: dict,
    extra_fields: Optional[list] = None,
) -> tuple[dict, dict]:
    """Get all available entities within a ShotGrid Project.

    We check with ShotGrid to see what entities are enabled in a given project,
    then we build two dictionaries, one containing all entities with their ID
    as key and the representation as the value, and another dictionary where we
    store all the children on an entity, the key is the parent entity, and the
    value a list of it's children; all this by querying all the existing
    entities in a project for the enabled entities.

    Note: Asset Categories in ShotGrid aren't entities per se, or at least not
    queryable from the API, so we treat them as folders.

    Args:
        sg_session (shotgun_api3.Shotgun): Shotgun Session object.
        sg_project (dict): The ShotGrid project to query its entities.
        sg_enabled_entities (list): List of ShotGrid entities to query.
        project_code_field (str): The ShotGrid project code field.
        custom_attribs_map (dict): Dictionary that maps names of attributes in
            AYON to ShotGrid equivalents.
        extra_fields (list): List of extra fields to pass to the query.

    Returns:
        tuple(
            entities_by_id (dict): A dict containing all entities with
                their ID as key.
            entities_by_parent_id (dict): A dict containing all entities
                that have children.
        )

    """
    query_fields = list(SG_COMMON_ENTITY_FIELDS)

    if extra_fields and isinstance(extra_fields, list):
        query_fields += extra_fields

    for sg_attrib in custom_attribs_map.values():
        query_fields.extend([f"sg_{sg_attrib}", sg_attrib])

    project_enabled_entities = get_sg_project_enabled_entities(
        sg_session,
        sg_project,
        sg_enabled_entities
    )

    if not project_code_field:
        project_code_field = "code"

    # TODO: Add support to sync versions too
    entities_to_ignore = ["Version"]

    sg_ay_dicts = {
        sg_project["id"]: _sg_to_ay_dict(
            sg_project,
            project_code_field,
            custom_attribs_map,
        ),
    }

    sg_ay_dicts_parents: Dict[str, set] = (
        collections.defaultdict(set)
    )

    for enabled_entity in project_enabled_entities:
        entity_name, parent_field = enabled_entity

        # Potential fix when shotgrid api returns the same entity more than
        # once, we store the entities in a dictionary to avoid duplicates
        if entity_name in entities_to_ignore:
            continue

        sg_entities = sg_session.find(
            entity_name,
            filters=[["project", "is", sg_project]],
            fields=query_fields,
        )

        for sg_entity in sg_entities:
            parent_id = sg_project["id"]

            if (
                parent_field != "project"
                and sg_entity[parent_field]
                and entity_name != "Asset"
            ):
                parent_id = sg_entity[parent_field]["id"]

            elif entity_name == "Asset" and sg_entity["sg_asset_type"]:
                # Asset Categories (sg_asset_type) are not entities
                # (or at least aren't queryable) in ShotGrid
                # thus here we create common folders.
                asset_category = sg_entity["sg_asset_type"]
                # asset category entity name
                cat_ent_name = slugify_string(asset_category).lower()

                if cat_ent_name not in sg_ay_dicts:
                    asset_category_entity = {
                        "label": asset_category,
                        "name": cat_ent_name,
                        "attribs": {
                            SHOTGRID_ID_ATTRIB: slugify_string(
                                asset_category).lower(),
                            SHOTGRID_TYPE_ATTRIB: "AssetCategory",
                        },
                        "data": {
                            CUST_FIELD_CODE_ID: None,
                            CUST_FIELD_CODE_SYNC: None,
                        },
                        "type": "folder",
                        "folder_type": "AssetCategory",
                    }
                    sg_ay_dicts[cat_ent_name] = asset_category_entity
                    sg_ay_dicts_parents[sg_project["id"]].add(cat_ent_name)

                parent_id = cat_ent_name

            sg_ay_dict = _sg_to_ay_dict(
                sg_entity,
                project_code_field,
                custom_attribs_map,
            )

            sg_id = sg_ay_dict["attribs"][SHOTGRID_ID_ATTRIB]
            sg_ay_dicts[sg_id] = sg_ay_dict
            sg_ay_dicts_parents[parent_id].add(sg_id)

    return sg_ay_dicts, sg_ay_dicts_parents


def get_sg_entity_as_ay_dict(
    sg_session: shotgun_api3.Shotgun,
    sg_type: str,
    sg_id: int,
    project_code_field: str,
    custom_attribs_map: Optional[Dict[str, str]] = None,
    extra_fields: Optional[list] = None,
    retired_only: Optional[bool] = False,
) -> dict:
    """Get a ShotGrid entity, and morph it to an AYON compatible one.

    Args:
        sg_session (shotgun_api3.Shotgun): Shotgun Session object.
        sg_type (str): The ShotGrid entity type.
        sg_id (int): ShotGrid ID of the entity to query.
        project_code_field (str): The ShotGrid project code field.
        custom_attribs_map (Optional[dict]): Dictionary that maps names of
            attributes in AYON to ShotGrid equivalents.
        extra_fields (Optional[list]): List of optional fields to query.
        retired_only (bool): Whether to return only retired entities.
    Returns:
        new_entity (dict): The ShotGrid entity ready for AYON consumption.
    """
    query_fields = list(SG_COMMON_ENTITY_FIELDS)
    if extra_fields and isinstance(extra_fields, list):
        query_fields.extend(extra_fields)
    else:
        extra_fields = []

    # If custom attributes are passed, query each of them
    # NOTE: we query both with the prefix "sg_" and without
    # to account for the fact that some attributes are built-in
    # and some aren't in SG
    if custom_attribs_map:
        for sg_attrib in custom_attribs_map.values():
            query_fields.extend([f"sg_{sg_attrib}", sg_attrib])

    if project_code_field not in query_fields:
        query_fields.append(project_code_field)

    sg_entity = sg_session.find_one(
        sg_type,
        filters=[["id", "is", sg_id]],
        fields=query_fields,
        retired_only=retired_only
    )

    if not sg_entity:
        return {}

    sg_ay_dict = _sg_to_ay_dict(
        sg_entity, project_code_field, custom_attribs_map
    )

    for field in extra_fields:
        sg_value = sg_entity.get(field)
        # If no value in SG entity skip
        if sg_value is None:
            continue

        sg_ay_dict["data"][field] = sg_value

    return sg_ay_dict


def get_sg_entity_parent_field(
    sg_session: shotgun_api3.Shotgun,
    sg_project: dict,
    sg_entity_type: str,
    sg_enabled_entities: list
) -> str:
    """Find the ShotGrid entity field that points to its parent.

    This is handy since there is really no way to tell the parent entity of
    a ShotGrid entity unless you don't know this field, and it can change based
    on projects and their Tracking Settings.

    Args:
        sg_session (shotgun_api3.Shotgun): ShotGrid Session object.
        sg_project (dict): ShotGrid Project dict representation.
        sg_entity_type (str): ShotGrid Entity type.

    Returns:
        sg_parent_field (str): The field that points to the entity parent.
    """
    sg_parent_field = ""

    for entity_tuple in get_sg_project_enabled_entities(
        sg_session, sg_project, sg_enabled_entities
    ):
        entity_type, parent_field = entity_tuple

        if entity_type == sg_entity_type:
            sg_parent_field = parent_field

    return sg_parent_field


def get_sg_missing_ay_attributes(sg_session: shotgun_api3.Shotgun):
    """ Ensure all the AYON required fields are present in ShotGrid.

    Args:
        sg_session (shotgun_api3.Shotgun): Instance of a ShotGrid API Session.

    Returns:
        missing_attrs (list): Contains any missing attribute, if any.
    """
    missing_attrs = []
    for ayon_attr, attr_dict in SG_PROJECT_ATTRS.items():
        try:
            sg_session.schema_field_read(
                "Project",
                field_name=f"sg_{ayon_attr}"
            )
        except Exception:
            # shotgun_api3.shotgun.Fault: API schema_field_read()
            missing_attrs.append(ayon_attr)

    return missing_attrs


def get_sg_project_by_id(
    sg_session: shotgun_api3.Shotgun,
    project_id: int,
    extra_fields: Optional[list] = None
) -> dict:
    """ Find a project in ShotGrid by its id.

    Args:
        sg_session (shotgun_api3.Shotgun): Shotgun Session object.
        project_id (int): The project ID to look for.
        extra_fields (Optional[list]): List of optional fields to query.
    Returns:
        sg_project (dict): ShotGrid Project dict.
     """
    common_fields = list(SG_COMMON_ENTITY_FIELDS)

    if extra_fields:
        common_fields.extend(extra_fields)

    sg_project = sg_session.find_one(
        "Project",
        [["id", "is", project_id]],
        fields=common_fields,
    )

    if not sg_project:
        raise ValueError(f"Unable to find project {project_id} in ShotGrid.")

    return sg_project


def get_sg_project_by_name(
    sg_session: shotgun_api3.Shotgun,
    project_name: str,
    custom_fields: list = None,
) -> dict:
    """ Find a project in ShotGrid by its name.

    Args:
        sg_session (shotgun_api3.Shotgun): Shotgun Session object.
        project_name (str): The project name to look for.
    Returns:
        sg_project (dict): ShotGrid Project dict.
    """
    common_fields = ["id", "code", "name", "sg_status"]

    if custom_fields and isinstance(custom_fields, list):
        common_fields += custom_fields

    sg_project = sg_session.find_one(
        "Project",
        [["name", "is", project_name]],
        fields=common_fields,
    )

    if not sg_project:
        raise ValueError(f"Unable to find project {project_name} in ShotGrid.")

    return sg_project


def get_sg_project_enabled_entities(
    sg_session: shotgun_api3.Shotgun,
    sg_project: dict,
    sg_enabled_entities: list,
) -> list:
    """Function to get all enabled entities in a project.

    ShotGrid allows a lot of flexibility when it comes to hierarchies, here we
    find all the enabled entity type (Shots, Sequence, etc) in a specific
    project and provide the configured field that points to the parent entity.

    Args:
        sg_session (shotgun_api3.Shotgun): Shotgun Session object.
        project_name (str): The project name to look for.

    Returns:
        project_entities (list[tuple(entity type, parent field)]): List of
            enabled entities names and their respective parent field.
    """
    sg_project = sg_session.find_one(
        "Project",
        filters=[["id", "is", sg_project["id"]]],
        fields=["tracking_settings"]
    )

    if not sg_project:
        log.error(
            f"Unable to find {sg_project} in the ShotGrid instance."
        )
        return []

    sg_project_schema = sg_session.schema_entity_read(
        project_entity=sg_project
    )

    project_navigation = sg_project["tracking_settings"]["navchains"]
    project_navigation["Task"] = "entity"

    project_entities = []

    for sg_entity_type in sg_enabled_entities:
        if sg_entity_type == "Project":
            continue

        is_entity_enabled = sg_project_schema.get(
            sg_entity_type, {}
        ).get("visible", {}).get("value", False)

        if is_entity_enabled:
            parent_field = project_navigation.get(sg_entity_type, None)

            if parent_field and parent_field != "__flat__":
                if "," in parent_field:
                    # This catches instances where the Hierarchy is set to
                    # something like "Seq > Scene > Shot" which returns
                    # a string like so: 'sg_scene,Scene.sg_sequence' and
                    # confusing enough we want the first element to be
                    # the parent.
                    parent_field = parent_field.split(",")[0]

                project_entities.append((
                    sg_entity_type,
                    parent_field.replace(f"{sg_entity_type}.", "")
                ))
            else:
                project_entities.append((sg_entity_type, "project"))

    return project_entities


def get_sg_statuses(
    sg_session: shotgun_api3.Shotgun,
    sg_entity_type: Optional[str] = None
) -> dict:
    """ Get all supported ShotGrid Statuses.

    Args:
        sg_session (shotgun_api3.Shotgun): ShotGrid Session object.
        sg_entity_type (str): ShotGrid Entity type.

    Returns:
        sg_statuses (dict[str, str]): ShotGrid Project Statuses dictionary
            mapping the status short code and its long name.
    """
    # If given an entity type, we filter out the statuses by just the ones
    # supported by that entity
    # NOTE: this is a limitation in AYON as the statuses are global and not
    # per entity
    if sg_entity_type:
        if sg_entity_type == "Project":
            status_field = "sg_status"
        else:
            status_field = "sg_status_list"
        entity_status = sg_session.schema_field_read(sg_entity_type, status_field)
        sg_statuses = entity_status["sg_status_list"]["properties"]["display_values"]["value"]
        return sg_statuses

    sg_statuses = {
        status["code"]: status["name"]
        for status in sg_session.find("Status", [], fields=["name", "code"])
    }
    return sg_statuses


def get_sg_tags(
    sg_session: shotgun_api3.Shotgun
) -> dict:
    """ Get all tags on a ShotGrid project.

    Args:
        sg_session (shotgun_api3.Shotgun): ShotGrid Session object.
        sg_entity_type (str): ShotGrid Entity type.

    Returns:
        sg_tags (dict[str, str]): ShotGrid Project tags dictionary
            mapping the tag name to its id.
    """
    sg_tags = {
        tags["name"].lower(): tags["id"]
        for tags in sg_session.find("Tag", [], fields=["name", "id"])
    }
    return sg_tags


def get_sg_pipeline_steps(
    sg_session: shotgun_api3.Shotgun,
    shotgrid_project: dict,
    sg_enabled_entities: list,
) -> list:
    """ Get all pipeline steps on a ShotGrid project.

    Args:
        sg_session (shotgun_api3.Shotgun): ShotGrid Session object.
        shotgrid_project (dict): The project owning the Pipeline steps.
    Returns:
        sg_steps (list): ShotGrid Project Pipeline Steps list.
    """
    sg_steps = []
    enabled_entities = get_sg_project_enabled_entities(
        sg_session,
        shotgrid_project,
        sg_enabled_entities
    )

    pipeline_steps = sg_session.find(
        "Step",
        filters=[{
                "filter_operator": "any",
                "filters": [
                    ["entity_type", "is", entity]
                    for entity, _ in enabled_entities
                ]
            }],
        fields=["code", "short_name", "entity_type"]
    )

    for step in pipeline_steps:
        sg_steps.append((step["code"], step["short_name"].lower()))

    sg_steps = list(set(sg_steps))
    return sg_steps


def get_sg_custom_attributes_data(
    sg_session: shotgun_api3.Shotgun,
    ay_attribs: dict,
    sg_entity_type: str,
    custom_attribs_map: dict,
) -> dict:
    """Get a dictionary with all the extra attributes we want to sync to SG

    Args:
        sg_session (shotgun_api3.Shotgun): Instance of a Shotgrid API Session.
        ay_attribs (dict): Dictionary that contains the ground truth data of
            attributes that we want to sync to SG.
        sg_entity_type (str): ShotGrid Entity type.
        custom_attribs_map (dict): Dictionary that maps names of attributes in
            AYON to ShotGrid equivalents.
    """
    data_to_update = {}
    for ay_attrib, sg_attrib in custom_attribs_map.items():
        attrib_value = ay_attribs.get(ay_attrib)
        if attrib_value is None:
            continue

        # try it first without `sg_` prefix since some are built-in
        exists = check_sg_attribute_exists(
            sg_session, sg_entity_type, sg_attrib, check_writable=True
        )
        # and then with the prefix
        if not exists:
            sg_attrib = f"sg_{sg_attrib}"
            exists = check_sg_attribute_exists(
                sg_session, sg_entity_type, sg_attrib, check_writable=True
            )

        if exists:
            data_to_update[sg_attrib] = attrib_value

    return data_to_update


def update_ay_entity_custom_attributes(
    ay_entity: Union[ProjectEntity, FolderEntity, TaskEntity],
    sg_ay_dict: dict,
    custom_attribs_map: dict,
    values_to_update: Optional[list] = None,
):
    """Update AYON entity custom attributes from ShotGrid dictionary"""
    for ay_attrib, _ in custom_attribs_map.items():
        if values_to_update and ay_attrib not in values_to_update:
            continue

        attrib_value = sg_ay_dict["attribs"].get(ay_attrib)
        if attrib_value is None:
            continue

        if ay_attrib == "tags":
            log.warning("Tags update is not supported yet.")
            ay_entity.tags = [tag["name"] for tag in attrib_value]
        elif ay_attrib == "status":
            # TODO: Implement status update
            try:
                # INFO: it was causing error so trying to set status directly
                ay_entity.status = attrib_value
            except ValueError as e:
                # `ValueError: Status ip is not available on project.`
                log.warning(f"Status sync not implemented: {e}")
        else:
            ay_entity.attribs.set(ay_attrib, attrib_value)


def create_new_ayon_entity(
    sg_session: shotgun_api3.Shotgun,
    entity_hub: ayon_api.entity_hub.EntityHub,
    parent_entity: Union[ProjectEntity, FolderEntity],
    sg_ay_dict: Dict
):
    """Helper method to create entities in the EntityHub.

    Task Creation:
        https://github.com/ynput/ayon-python-api/blob/30d702618b58676c3708f09f131a0974a92e1002/ayon_api/entity_hub.py#L284

    Folder Creation:
        https://github.com/ynput/ayon-python-api/blob/30d702618b58676c3708f09f131a0974a92e1002/ayon_api/entity_hub.py#L254

    Args:
        entity_hub (ayon_api.EntityHub): The project's entity hub.
        parent_entity: AYON parent entity.
        sg_ay_dict (dict): AYON ShotGrid entity to create.

    Returns:
        FolderEntity|TaskEntity: Added task entity.
    """
    if sg_ay_dict["type"].lower() == "task":
        if parent_entity.entity_type == "project":
            log.warning("Cannot create task directly under project")
            return

        ay_entity = entity_hub.add_new_task(
            task_type=sg_ay_dict["task_type"],
            name=sg_ay_dict["name"],
            label=sg_ay_dict["label"],
            entity_id=sg_ay_dict["data"][CUST_FIELD_CODE_ID],
            parent_id=parent_entity.id,
            attribs=sg_ay_dict["attribs"]
        )
    else:
        ay_entity = entity_hub.add_new_folder(
            folder_type=sg_ay_dict["folder_type"],
            name=sg_ay_dict["name"],
            label=sg_ay_dict["label"],
            entity_id=sg_ay_dict["data"][CUST_FIELD_CODE_ID],
            parent_id=parent_entity.id,
            attribs=sg_ay_dict["attribs"]
        )

    log.debug(f"Created new AYON entity: {ay_entity}")
    ay_entity.attribs.set(
        SHOTGRID_ID_ATTRIB,
        sg_ay_dict["attribs"].get(SHOTGRID_ID_ATTRIB, "")
    )
    ay_entity.attribs.set(
        SHOTGRID_TYPE_ATTRIB,
        sg_ay_dict["attribs"].get(SHOTGRID_TYPE_ATTRIB, "")
    )

    try:
        entity_hub.commit_changes()

        sg_session.update(
            sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB],
            sg_ay_dict["attribs"][SHOTGRID_ID_ATTRIB],
            {
                CUST_FIELD_CODE_ID: ay_entity.id
            }
        )
    except Exception:
        log.error("AYON Entity could not be created", exc_info=True)

    return ay_entity
