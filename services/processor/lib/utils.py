import copy

import shotgun_api3

from .constants import AYON_SHOTGRID_ENTITY_MAP, SHOTGRID_PROJECT_ATTRIBUTES


def get_shotgrid_entities(sg, project):
    entity_fields = {
        "Project": ["name", "code", "tags", "sg_status"],
        "Episode": ["code", "type", "project.name", "sg_status_list", "tags"],
        "Sequence": ["name", "code", "sg_status_list", "tags", "episode"],
        "Shot": ["name", "code", "sg_status_list", "tags", "sg_sequence", "episode"],
        "Asset": ["code", "sg_status_list", "tags"],
        "Version": ["code", "sg_status_list", "tags"],
    }

    project_enabled_entities = get_shotgrid_project_entities(sg, project)
    project_enabled_entities.remove("Task")
    # TODO: Implement Versions...
    project_enabled_entities.remove("Version")

    project_entities_by_id = {
        project["id"]: project,
    }
    project_entities_by_parent_id = {}

    for enabled_entity in project_enabled_entities:
        entities = sg.find(
            enabled_entity,
            filters=[["project", "is", project]],
            fields=entity_fields.get(enabled_entity, [])
        )

        if entities:
            for entity in entities:
                project_entities_by_id[entity["id"]] = entity
                parent_id = project["id"]

                if entity["type"] == "Shot":
                    # Parents could be "Project", "Episode" or "Sequence"... ?
                    if entity.get("sg_sequence", {}):
                        parent_id = entity["sg_sequence"]["id"]
                    elif entity.get("episode", {}):
                        parent_id = entity["episode"]["id"]
                    else:
                        parent_id = project["id"]

                elif entity["type"] == "Sequence":
                    if entity.get("episode", {}):
                        parent_id = entity["episode"]["id"]
                    else:
                        parent_id = project["id"]

                project_entities_by_parent_id.setdefault(parent_id, [])
                project_entities_by_parent_id[parent_id].append(entity)

    return project_entities_by_id, project_entities_by_parent_id


def get_shotgrid_project_hierarchy(sg, project):
    sg_entities_by_id, sg_entities_by_parent_id = get_shotgrid_entities(sg, project)

    hierarchical_project = copy.deepcopy(project)
    hierarchical_project.update({
        "has_children": False,
        "children": [],
    })

    for parent_id, children in sg_entities_by_parent_id.items():
        parent_type = sg_entities_by_id[parent_id]["type"]

        if parent_type == "Project":
            _append_children(hierarchical_project, children)

        elif parent_type == "Episode":
            for project_child in hierarchical_project["children"]:
                if project_child["type"] == "Episode" and project_child["id"] == parent_id:
                    _append_children(project_child, children)

        elif parent_type == "Sequence":
            for project_child in hierarchical_project["children"]:
                if project_child["type"] == "Episode":
                    if not project_child.get("has_children"):
                        continue

                    for episode_child in project_child["children"]:
                        if episode_child["type"] == "Sequence" and episode_child["id"] == parent_id:
                            _append_children(episode_child, children)

                elif project_child["type"] == "Sequence" and project_child["id"] == parent_id:
                    _append_children(project_child, children)

    return hierarchical_project, sg_entities_by_id, sg_entities_by_parent_id


def _append_children(parent_entity, children_to_add):
    parent_entity["has_children"] = True
    parent_entity.setdefault("children", [])

    for child in children_to_add:
        if child not in parent_entity["children"]:
            parent_entity["children"].append(child)


def get_shotgrid_project_entities(sg, shotgun_project):
    print(shotgun_project)
    sg_project = sg.find_one("Project", filters=[["id", "is", shotgun_project["id"]]])

    if not sg_project:
        return

    sg_project_schema = sg.schema_entity_read(project_entity=shotgun_project)

    project_entities = []

    for entity in AYON_SHOTGRID_ENTITY_MAP:
        if entity == "Project":
            continue

        if sg_project_schema.get(entity, {}).get("visible", {}).get("value", False):
            project_entities.append(entity)

    return project_entities


def get_shotgrid_custom_attributes_config():
    pass

def get_shotgrid_project_by_name(sg: shotgun_api3.Shotgun, project_name,) -> dict:
    sg_project = sg.find_one(
        "Project",
        [["name", "is", project_name]],
        fields=["id", "code", "name", "sg_status"]
    )

    if not sg_project:
        raise ValueError(f"Unable to find project {project_name} in ShotGrid.")

    return sg_project


def get_shotgrid_project_by_id(sg: shotgun_api3.Shotgun, project_id) -> dict:
    sg_project = sg.find_one(
        "Project",
        [["id", "is", project_id]],
        fields=["id", "code", "name", "sg_status"]
    )

    if not sg_project:
        raise ValueError(f"Unable to find project {project_id} in ShotGrid.")

    return sg_project


def get_shotgrid_tasks(shotgrid_session: shotgun_api3.Shotgun, shotgrid_project: dict) -> list:
    """Ensure the Ayon project has all the required Tasks from Shotgird."""
    sg_tasks = []

    for task in shotgrid_session.find(
        "Task",
        [["project", "is", shotgrid_project]],
        fields=["content", "step", "sg_status", "tags"]
    ):
        if task["content"] not in sg_tasks:
            sg_tasks.append(task["content"])

    return sg_tasks


def get_shotgrid_statuses(shotgrid_session: shotgun_api3.Shotgun, shotgrid_project: dict) -> dict:
    """Ensure the Ayon project has all the required Statuses from Shotgrid."""
    sg_statuses = {}

    # These are the entities that have statuses in SG
    for entity in ["Episode", "Sequence", "Shot", "Asset", "Task"]:
        for status_schema in shotgrid_session.schema_field_read(
            entity,
            "sg_status_list"
        ):
            statuses = status_schema["sg_status_list"]["properties"]["display_values"]["value"]
            for short_name, display_name in statuses.items():
                sg_statuses.setdefault(short_name, display_name)

    return sg_statuses

