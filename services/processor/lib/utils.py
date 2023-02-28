import copy

import shotgun_api3

from .constants import AYON_SHOTGRID_ENTITY_MAP


def get_shotgrid_entities(
    shotgrid_session: shotgun_api3.Shotgun, shotgun_project: dict, custom_fields: list
) -> tuple(dict, dict):
    """Get all available entities within a Shotgrid Project.

    Args:
        shotgrid_session (shotgun_api3.Shotgun): Shotgun Session object.
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
    common_fields = ["code", "name", "sg_status", "sg_status_list", "tags"]

    if custom_fields and isinstance(custom_fields, list):
        common_fields = common_fields + custom_fields

    entity_fields = {
        "Project": common_fields,
        "Episode": common_fields + ["type"],
        "Sequence": common_fields + ["episode"],
        "Shot": common_fields + ["sg_sequence", "episode"],
        "Asset": common_fields + ["shots"],
        "Version": common_fields,
    }

    project_enabled_entities = get_shotgrid_project_entities(shotgrid_session, shotgun_project)
    project_enabled_entities.remove("Task")
    # TODO: Implement Versions...
    project_enabled_entities.remove("Version")

    entities_by_id = {
        shotgun_project["id"]: shotgun_project,
    }
    entities_by_parent_id = {}

    for enabled_entity in project_enabled_entities:
        entities = shotgrid_session.find(
            enabled_entity,
            filters=[["project", "is", shotgun_project]],
            fields=entity_fields.get(enabled_entity, []),
        )

        if entities:
            for entity in entities:
                entities_by_id[entity["id"]] = entity
                parent_id = shotgun_project["id"]

                if entity["type"] == "Shot":
                    # Parents could be "Project", "Episode" or "Sequence"... ?
                    if entity.get("sg_sequence", {}):
                        parent_id = entity["sg_sequence"]["id"]
                    elif entity.get("episode", {}):
                        parent_id = entity["episode"]["id"]
                    else:
                        parent_id = shotgun_project["id"]

                elif entity["type"] == "Sequence":
                    if entity.get("episode", {}):
                        parent_id = entity["episode"]["id"]
                    else:
                        parent_id = shotgun_project["id"]

                entities_by_parent_id.setdefault(parent_id, [])
                entities_by_parent_id[parent_id].append(entity)

    return entities_by_id, entities_by_parent_id


def get_shotgrid_project_hierarchy(
    shotgrid_session: shotgun_api3.Shotgun, shotgun_project: dict
) -> dict:
    """A Shotgrid project represented as a dict with hierarchy.

    The hierarchy goes down to the Shot/Asset level.

    Args:
        shotgrid_session (shotgun_api3.Shotgun): Shotgun Session object.
        project_name (str): The project name to look for.

    Returns:
        hierarchical_project (dict): Shotgrid project as a dict.

    Example:
        {
            "type": "Project",
            "id": 122,
            "has_children": true,
            "children": [
                {
                "type": "Episode",
                "id": 4,
                "code": "ep101",
                "sg_status_list": null,
                "tags": [],
                "has_children": true,
                "children": [
                    {
                    "type": "Sequence",
                    "id": 41,
                    "code": "seq101",
                    "sg_status_list": "ip",
                    "tags": [],
                    "episode": {
                        "id": 4,
                        "name": "ep101",
                        "type": "Episode"
                    },
                    "has_children": true,
                    "children": [
                        {
                        "type": "Shot",
                        "id": 1174,
                        "code": "sh101",
                        "sg_status_list": "wtg",
                        "tags": [],
                        "sg_sequence": {
                            "id": 41,
                            "name": "seq101",
                            "type": "Sequence"
                        }
                        }
                    ]
                    }
                ]
                },
                {
                "type": "Shot",
                "id": 1207,
                "code": "sh101_020",
                "sg_status_list": "wtg",
                "tags": [],
                "sg_sequence": null
                }
            ]
        }
    """
    sg_entities_by_id, sg_entities_by_parent_id = get_shotgrid_entities(
        shotgrid_session, shotgun_project
    )

    hierarchical_project = copy.deepcopy(shotgun_project)
    hierarchical_project.update(
        {
            "has_children": False,
            "children": [],
        }
    )

    for parent_id, children in sg_entities_by_parent_id.items():
        parent_type = sg_entities_by_id[parent_id]["type"]

        if parent_type == "Project":
            _append_children(hierarchical_project, children)

        elif parent_type == "Episode":
            for project_child in hierarchical_project["children"]:
                if (
                    project_child["type"] == "Episode"
                    and project_child["id"] == parent_id
                ):
                    _append_children(project_child, children)

        elif parent_type == "Sequence":
            for project_child in hierarchical_project["children"]:
                if project_child["type"] == "Episode":
                    if not project_child.get("has_children"):
                        continue

                    for episode_child in project_child["children"]:
                        if (
                            episode_child["type"] == "Sequence"
                            and episode_child["id"] == parent_id
                        ):
                            _append_children(episode_child, children)

                elif (
                    project_child["type"] == "Sequence"
                    and project_child["id"] == parent_id
                ):
                    _append_children(project_child, children)

    return hierarchical_project, sg_entities_by_id, sg_entities_by_parent_id


def _append_children(parent_entity: dict, children_to_add: list[dict]):
    """Helper method that will add a given list into the key "children" of the
    provided dictionary.
    """
    parent_entity["has_children"] = True
    parent_entity.setdefault("children", [])

    for child in children_to_add:
        if child not in parent_entity["children"]:
            parent_entity["children"].append(child)


def get_shotgrid_project_entities(
    shotgrid_session: shotgun_api3.Shotgun, shotgun_project: dict
) -> list:
    """Function to get all enabled entities in a project.

    Args:
        shotgrid_session (shotgun_api3.Shotgun): Shotgun Session object.
        project_name (str): The project name to look for.

    Returns:
        project_entities (list): List of enabled entities names.
    """
    sg_project = shotgrid_session.find_one("Project", filters=[["id", "is", shotgun_project["id"]]])

    if not sg_project:
        return

    sg_project_schema = shotgrid_session.schema_entity_read(project_entity=shotgun_project)

    project_entities = []

    for entity in AYON_SHOTGRID_ENTITY_MAP:
        if entity == "Project":
            continue

        if sg_project_schema.get(entity, {}).get("visible", {}).get("value", False):
            project_entities.append(entity)

    return project_entities


def get_shotgrid_project_by_name(
    shotgrid_session: shotgun_api3.Shotgun,
    project_name: str,
) -> dict:
    """ Find a project in Shotgrid by its name.

    Args:
        shotgrid_session (shotgun_api3.Shotgun): Shotgun Session object.
        project_name (str): The project name to look for.
    Returns:
        sg_project (dict): Shotgrid Project dict.
     """
    sg_project = sg.find_one(
        "Project",
        [["name", "is", project_name]],
        fields=["id", "code", "name", "sg_status"],
    )

    if not sg_project:
        raise ValueError(f"Unable to find project {project_name} in ShotGrid.")

    return sg_project


def get_shotgrid_project_by_id(shotgrid_session: shotgun_api3.Shotgun, project_id: int) -> dict:
    """ Find a project in Shotgrid by its id.

    Args:
        shotgrid_session (shotgun_api3.Shotgun): Shotgun Session object.
        project_id (int): The project ID to look for.
    Returns:
        sg_project (dict): Shotgrid Project dict.
     """
    sg_project = sg.find_one(
        "Project",
        [["id", "is", project_id]],
        fields=["id", "code", "name", "sg_status"],
    )

    if not sg_project:
        raise ValueError(f"Unable to find project {project_id} in ShotGrid.")

    return sg_project


def get_shotgrid_tasks(
    shotgrid_session: shotgun_api3.Shotgun, shotgrid_project: dict
) -> list:
    """ Get all Tasks on a Shotgrid project.

    Args:
        shotgrid_session (shotgun_api3.Shotgun): Shotgun Session object.
        shotgrid_project (dict): The project owning the Tasks.
    Returns:
        sg_tasks (list): Shotgrid Project Tasks list.
     """
    sg_tasks = []

    for task in shotgrid_session.find(
        "Task",
        [["project", "is", shotgrid_project]],
        fields=["content", "step", "sg_status", "tags"],
    ):
        if task["content"] not in sg_tasks:
            sg_tasks.append(task["content"])

    return sg_tasks


def get_shotgrid_statuses(
    shotgrid_session: shotgun_api3.Shotgun, shotgrid_project: dict
) -> dict:
    """ Get all Statuses on a Shotgrid project.

    Args:
        shotgrid_session (shotgun_api3.Shotgun): Shotgun Session object.
        shotgrid_project (dict): The project owning the Tasks.
    Returns:
        sg_statuses (dict): Shotgrid Project Statuses list.
     """
    sg_statuses = {}

    # These are the entities that have statuses in SG
    for entity in ["Episode", "Sequence", "Shot", "Asset", "Task"]:
        for status_schema in shotgrid_session.schema_field_read(
            entity, "sg_status_list"
        ):
            statuses = status_schema["sg_status_list"]["properties"]["display_values"][
                "value"
            ]
            for short_name, display_name in statuses.items():
                sg_statuses.setdefault(short_name, display_name)

    return sg_statuses

