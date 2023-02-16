import shotgun_api3


def get_shotgrid_hierarchy(shotgrid_session: shotgun_api3.Shotgun) -> dict:
    entity_fields = {
        "Project": ["name", "code", "tags", "sg_status"],
        "Episode": ["code", "type", "project.name", "sg_status_list", "tags"],
        "Sequence": ["name", ],
        "Shot": [],
        "Asset": [],
        "Version": [],
        "Task": ["content", "step", "sg_status_list", "tags"]
    }

    sg_project_dict = shotgrid_session.nav_expand(f"/Project/{project_id}")
    _populate_nested_children(sg_project_dict, entity_fields=entity_fields)
    return sg_project_dict


def _populate_nested_children(sg_dict, entity_fields=None):
    if sg_dict["has_children"]:
        for children_index, children in enumerate(sg_dict["children"]):
            if children.get("path"):
                sg_dict["children"][children_index] = sg.nav_expand(
                    children["path"], entity_fields=entity_fields)
                _populate_nested_children(sg_dict["children"][children_index])


def get_shotgrid_project_by_name(sg: shotgun_api3.Shotgun, project_name,) -> dict:
    sg_project = sg.find_one(
        "Project",
        [["name", "is", project_name]],
        fields=["id", "code", "name", "sg_status"]
    )

    if not sg_project:
        raise ValueError(f"Unable to find project {project_name} in ShotGrid.")

    return sg_project


def get_shotgrid_project_by_id(sg: shotgun_api3.Shotgun, project_id,) -> dict:
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

