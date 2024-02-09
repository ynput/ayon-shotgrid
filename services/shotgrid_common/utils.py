import collections
from typing import Dict, Optional

from constants import (
    AYON_SHOTGRID_ENTITY_TYPE_MAP,
    CUST_FIELD_CODE_ID,
    CUST_FIELD_CODE_SYNC,
    SG_COMMON_ENTITY_FIELDS,
    SG_PROJECT_ATTRS,
    SHOTGRID_ID_ATTRIB,
    SHOTGRID_TYPE_ATTRIB,
)

from ayon_api.entity_hub import ProjectEntity
from ayon_api.utils import slugify_string
from nxtools import logging
import shotgun_api3


def _sg_to_ay_dict(sg_entity: dict, project_code_field=None) -> dict:
    """Morph a Shotgrid entity dict into an Ayon's Entity Hub compatible one.

    Create a dictionary that follows the Ayon Entity Hub schema and handle edge
    cases so it's ready for Ayon consumption.

    Folders: https://github.com/ynput/ayon-python-api/blob/30d702618b58676c3708f09f131a0974a92e1002/ayon_api/entity_hub.py#L2397
    Tasks: https://github.com/ynput/ayon-python-api/blob/30d702618b58676c3708f09f131a0974a92e1002/ayon_api/entity_hub.py#L2579

    Args:
        sg_entity (dict): Shotgun Entity dict representation.
    """
    if not project_code_field:
        project_code_field = "code"

    logging.debug(f"Transforming sg_entity '{sg_entity}' to ayon dict.")

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

    ay_dict = {
        "type": ay_entity_type, # In the EH there are either `folder_type` or `task_type`.
        "label": label,
        "name": name,
        "attribs": {
            SHOTGRID_ID_ATTRIB: sg_entity["id"],
            SHOTGRID_TYPE_ATTRIB: sg_entity["type"],
        },
        "data": {
            CUST_FIELD_CODE_SYNC: sg_entity.get(CUST_FIELD_CODE_SYNC, None),
            CUST_FIELD_CODE_ID: sg_entity.get(CUST_FIELD_CODE_ID, None),
        }
    }

    if task_type:
        ay_dict["task_type"] = task_type
    elif folder_type:
        ay_dict["folder_type"] = folder_type

    return ay_dict


def create_ay_fields_in_sg_entities(sg_session: shotgun_api3.Shotgun):
    """Create Ayon fields in Shotgrid entities.

    Some fields need to exist in the Shotgrid Entities, mainly the `sg_ayon_id`
    and `sg_ayon_sync_status` for the correct operation of the handlers.

    Args:
        sg_session (shotgun_api3.Shotgun): Instance of a Shotgrid API Session.
    """
    for sg_entity_type in AYON_SHOTGRID_ENTITY_TYPE_MAP:
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
                "description": "The Syncronization status with Ayon.",
                "valid_values": ["Synced", "Failed", "Skipped"],
            }
        )


def create_ay_fields_in_sg_project(sg_session: shotgun_api3.Shotgun):
    """Create Ayon Project fields in Shotgrid.

    This will create Project Unique attributes into Shotgrid.

    Args:
        sg_session (shotgun_api3.Shotgun): Instance of a Shotgrid API Session.
    """
    for attribute, attribute_values in SG_PROJECT_ATTRS.items():
        sg_field_name = attribute_values["name"]
        sg_field_code = attribute_values["sg_field"]
        sg_field_type = attribute_values["type"]
        sg_field_properties = {}

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


def create_sg_entities_in_ay(
    project_entity: ProjectEntity,
    sg_session: shotgun_api3.Shotgun,
    shotgrid_project: dict
):
    """Ensure Ayon has all the SG Steps (to use as task types) and Folder types.

    Args:
        project_entity (ProjectEntity): The ProjectEntity for a given project.
        sg_session (shotgun_api3.Shotgun): Shotgun Session object.
        shotgrid_project (dict): The project owning the Tasks.
    """
   
    # Types of SG entities to ignore as Ayon folders
    ignored_folder_types = {"task", "version"}

    # Find Shotgrid Entities that are to be treated as folders
    sg_folder_entities = [
        {"name": entity_type}
        for entity_type, _ in get_sg_project_enabled_entities(
            sg_session,
            shotgrid_project
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

    # Add Shotgrid Statuses to Project Entity
    for status in get_sg_statuses(sg_session):
        status_short_name, status_name = status
        project_entity.statuses.create(status_name, short_name=status_short_name)

    # Add Project task types by quering Shotgrid Pipeline steps
    sg_steps = [
        {"name": step[0], "shortName": step[1]}
        for step in get_sg_pipeline_steps(
            sg_session,
            shotgrid_project
        )
    ]
    new_task_types = sg_steps + project_entity.task_types
    new_task_types = list({
        task['name']: task
        for task in new_task_types
    }.values())
    project_entity.task_types = new_task_types

    return sg_folder_entities, sg_steps


def get_asset_category(entity_hub, parent_entity, asset_category_name):
    """ Look for existing "AssetCategory" folders in AYON.

        Asset categoried are not entities per se in Shotgrid, they are a "string"
        field in the `Asset` type, which is then used to visually group `Asset`s;
        here we attempt to find any `AssetCatgory` folder type that alread matches
        the one in Shotgrid.

    Args:
        entity_hub (ayon_api.EntityHub): The project's entity hub.
        parent_entity: Ayon parent entity.
        asset_category_name (str): The Asset Category name.
    """
    logging.debug(
        "It's an AssetCategory, checking if it exists already."
    )
    entity_hub.query_entities_from_server()
    asset_categories = [
        entity
        for entity in entity_hub.entities
        if entity.entity_type.lower() == "folder" and entity.folder_type == "AssetCategory"
    ]

    logging.debug(f"Found existing 'AssetCategory'(s)\n{asset_categories}")

    for asset_category in asset_categories:
        if (
            asset_category.name == asset_category_name
            and asset_category.parent.id == parent_entity.id
        ):
            logging.debug(f"AssetCategory already exists: {asset_category}")
            return asset_category

    logging.debug(f"Unable to find AssetCategory.")
    return None


def get_or_create_sg_field(
    sg_session: shotgun_api3.Shotgun,
    sg_entity_type: str,
    field_name: str,
    field_type: str,
    field_code: Optional[str] = None,
    field_properties: Optional[dict] = {}
):
    """Return a field from a Shotgrid Entity or create it if it doesn't exist.

    Args:
        sg_session (shotgun_api3.Shotgun): Instance of a Shotgrid API Session.
        sg_entity_type (str): The Shotgrid entity type the field belongs to.
        field_name (str): The Shotgrid field name, diplayed in the UI.
        field_type (str): The type of Shotgrid field.
        field_code (Optional[str]): The Shotgrid field code, infered from the
            the `field_name` if not provided.
        field_properties (Optional[dict]): Some fields allow extra properties,
            these can be defined with this argument.

    Returns:
        attribute_exists (str): The Field name (code).
    """
    attribute_exists = None

    if not field_code:
        field_code = f"sg_{field_name.lower().replace(' ', '_')}"

    try:
        attribute_exists = sg_session.schema_field_read(
            sg_entity_type,
            field_name=field_code
        )
        if attribute_exists:
            logging.debug(
                f"Shotgrid field {sg_entity_type} > {field_code} exists."
            )
            return attribute_exists

    except Exception:
        # shotgun_api3.shotgun.Fault: API schema_field_read()
        pass

    if not attribute_exists:
        logging.debug(
            f"Shotgrid field {sg_entity_type} > {field_code} does not exists."
        )

        try:
            attribute_exists = sg_session.schema_field_create(
                sg_entity_type,
                field_type,
                field_name,
                properties=field_properties,
            )
            logging.debug(
                f"Created Shotgrid field {sg_entity_type} > {field_code}"
            )
            return attribute_exists
        except Exception as e:
            logging.error(
                f"Can't create Shotgrid field {sg_entity_type} > {field_code}."
            )
            logging.error(e)

    return attribute_exists


def get_sg_entities(
    sg_session: shotgun_api3.Shotgun,
    sg_project: dict,
    custom_fields: Optional[list] = None,
    project_code_field: str = None,
) -> tuple[dict, dict]:
    """Get all available entities within a Shotgrid Project.

    We check with Shotgrid to see what entities are enabled in a given project,
    then we build two dictionaries, one containing all entities with their ID
    as key and the representation as the value, and another dictionay where we
    store all the children on an entity, the key is the parent entity, and the
    value a list of it's children; all this by querying all the existing
    entities in a project for the enabled entities.

    Note: Asset Categories in Shotgrid aren't entities per se, or at least not
    queryable from the API, so we treat them as folders.

    Args:
        sg_session (shotgun_api3.Shotgun): Shotgun Session object.
        project_name (str): The project name to look for.
        custom_fields (list): List of fields to pass to the query.

    Returns:
        tuple(
            entities_by_id (dict): A dict containing all entities with
                their ID as key.
            entities_by_parent_id (dict): A dict containing all entities
                that have children.
        )

    """
    common_fields = list(SG_COMMON_ENTITY_FIELDS)

    if custom_fields and isinstance(custom_fields, list):
        common_fields = common_fields + custom_fields

    project_enabled_entities = get_sg_project_enabled_entities(
        sg_session,
        sg_project
    )

    if not project_code_field:
        project_code_field = "code"

    entities_to_ignore = ["Version"]

    entities_by_id = {
        sg_project["id"]: _sg_to_ay_dict(
            sg_project,
            project_code_field=project_code_field
        ),
    }

    entities_by_parent_id: Dict[str, list] = (
        collections.defaultdict(list)
    )

    for enabled_entity in project_enabled_entities:
        entity_name, parent_field = enabled_entity

        if entity_name in entities_to_ignore:
            continue

        sg_entities = sg_session.find(
            entity_name,
            filters=[["project", "is", sg_project]],
            fields=common_fields,
        )
        if sg_entities:
            for entity in sg_entities:
                parent_id = sg_project["id"]

                if parent_field != "project" and entity[parent_field] and entity_name != "Asset":
                    parent_id = entity[parent_field]["id"]
                elif entity_name == "Asset" and entity["sg_asset_type"]:
                    # Asset Caregories (sg_asset_type) are not entities
                    # (or at least arent queryable) in Shotgrid
                    # thus here we create common folders.
                    asset_category = entity["sg_asset_type"]
                    asset_category_entity = {
                        "label": asset_category,
                        "name": slugify_string(asset_category).lower(),
                        "attribs": {
                            SHOTGRID_ID_ATTRIB: slugify_string(asset_category).lower(),
                            SHOTGRID_TYPE_ATTRIB: "AssetCategory",
                        },
                        "data": {
                            CUST_FIELD_CODE_ID: None,
                            CUST_FIELD_CODE_SYNC: None,
                        },
                        "type": "folder",
                        "folder_type": "AssetCategory",
                    }

                    if not entities_by_id.get(asset_category_entity["name"]):
                        entities_by_id[asset_category_entity["name"]] = asset_category_entity
                        entities_by_parent_id[sg_project["id"]].append(asset_category_entity)

                    parent_id = asset_category_entity["name"]

                entity = _sg_to_ay_dict(entity, project_code_field=project_code_field)
                entities_by_id[entity["attribs"][SHOTGRID_ID_ATTRIB]] = entity
                entities_by_parent_id[parent_id].append(entity)

    return entities_by_id, entities_by_parent_id


def get_sg_entity_as_ay_dict(
    sg_session: shotgun_api3.Shotgun,
    sg_type: str,
    sg_id: int,
    project_code_field: str,
    extra_fields: Optional[list] = None,
    retired_only: Optional[bool] = False,
    custom_attributes_map: Optional[dict] = None,
) -> dict:
    """Get a Shotgrid entity, and morph it to an Ayon compatible one.

    Args:
        sg_session (shotgun_api3.Shotgun): Shotgun Session object.
        sg_type (str): The Shotgrid entity type.
        sg_id (int): Shotgrid ID of the entity to query.
        extra_fields (Optional[list]): List of optional fields to query.

    Returns:
        new_entity (dict): The Shotgrid entity ready for Ayon consumption.
    """
    query_fields = list(SG_COMMON_ENTITY_FIELDS)
    if extra_fields and isinstance(extra_fields, list):
        query_fields.extend(extra_fields)
    else:
        extra_fields = []

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

    new_entity = _sg_to_ay_dict(sg_entity, project_code_field)

    for field in extra_fields:
        if field in ["name", "label", "sg_status_list"]:
            continue

        if custom_attributes_map and field in custom_attributes_map.values():
            for ay_attr, sg_attr in custom_attributes_map.items():
                if field == sg_attr:
                    new_entity["attribs"][ay_attr] = sg_entity.get(field)
        else:
            new_entity["data"][field] = sg_entity.get(field)

    return new_entity


def get_sg_entity_parent_field(
    sg_session: shotgun_api3.Shotgun,
    sg_project: dict,
    sg_entity_type: str
) -> str:
    """Find the Shotgrid entity field that points to its parent.

    This is handy since there is really no way to tell the parent entity of
    a Shotgrid entity unless you don't know this field, and it can change based
    on projects and their Tracking Settings.

    Args:
        sg_session (shotgun_api3.Shotgun): Shotgun Session object.
        sg_project (dict): Shotgun Project dict representation.
        sg_entity_type (str): Shotgun Entity type.

    Returns:
        sg_parent_field (str): The field that points to the entity parent.
    """
    sg_parent_field = ""

    for entity_tuple in get_sg_project_enabled_entities(sg_session, sg_project):
        entity_type, parent_field = entity_tuple

        if entity_type == sg_entity_type:
            sg_parent_field = parent_field

    return sg_parent_field


def get_sg_missing_ay_attributes(sg_session: shotgun_api3.Shotgun):
    """ Ensure all the Ayon required fields are present in Shotgrid.

    Args:
        sg_session (shotgun_api3.Shotgun): Instance of a Shotgrid API Session.

    Returns:
        missing_attrs (list): Contains any missing attriubte, if any.
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
    """ Find a project in Shotgrid by its id.

    Args:
        sg_session (shotgun_api3.Shotgun): Shotgun Session object.
        project_id (int): The project ID to look for.
        extra_fields (Optional[list]): List of optional fields to query.
    Returns:
        sg_project (dict): Shotgrid Project dict.
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
    """ Find a project in Shotgrid by its name.

    Args:
        sg_session (shotgun_api3.Shotgun): Shotgun Session object.
        project_name (str): The project name to look for.
    Returns:
        sg_project (dict): Shotgrid Project dict.
    """
    common_fields = ["id", "code", "name", "sg_status"]

    if custom_fields and isinstance(custom_fields, list):
        common_fields = common_fields + custom_fields

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
    sg_project: dict
) -> list:
    """Function to get all enabled entities in a project.

    Shotgrid allows a lot of flexibility when it comes to hierarchies, here we
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
        logging.error(
            f"Unable to find {sg_project} in the Shotgrid instance."
        )
        return []

    sg_project_schema = sg_session.schema_entity_read(
        project_entity=sg_project
    )

    project_navigation = sg_project["tracking_settings"]["navchains"]
    project_navigation["Task"] = "entity"

    project_entities = []

    for sg_entity_type in AYON_SHOTGRID_ENTITY_TYPE_MAP:
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
                    # something like "Seq > Secene > Shot" which returns a string
                    # like so: 'sg_scene,Scene.sg_sequence' and confusing enough
                    # we want the first element to be the parent.
                    parent_field = parent_field.split(",")[0]

                project_entities.append((
                    sg_entity_type,
                    parent_field.replace(f"{sg_entity_type}.", "")
                ))
            else:
                project_entities.append((sg_entity_type, "project"))

    logging.debug(f"Project {sg_project} enabled entities: {project_entities}")
    return project_entities


def get_sg_statuses(sg_session: shotgun_api3.Shotgun) -> dict:
    """ Get all Statuses on a Shotgrid project.

    Args:
        sg_session (shotgun_api3.Shotgun): Shotgun Session object.

    Returns:
        sg_statuses (list[tuple()]): Shotgrid Project Statuses list of tuples.
    """

    sg_statuses = [
        (status["code"], status["name"])
        for status in sg_session.find("Status", [], fields=["name", "code"])
    ]
    logging.debug(f"Shotgrid Statuses: {sg_statuses}")
    return sg_statuses


def get_sg_pipeline_steps(
    sg_session: shotgun_api3.Shotgun,
    shotgrid_project: dict
) -> list:
    """ Get all pipeline steps on a Shotgrid project.

    Args:
        sg_session (shotgun_api3.Shotgun): Shotgrid Session object.
        shotgrid_project (dict): The project owning the Pipeline steps.
    Returns:
        sg_steps (list): Shotgrid Project Pipeline Steps list.
    """
    sg_steps = []

    enabled_entities = get_sg_project_enabled_entities(
        sg_session,
        shotgrid_project
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
    logging.debug(f"Shotgrid Pipeline Steps: {sg_steps}")
    return sg_steps

