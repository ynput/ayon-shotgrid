import shotgun_api3

from .constants import AYON_SHOTGRID_ENTITY_MAP, SHOTGRID_PROJECT_ATTRIBUTES


def project_hierarchy_encore(sg, project):
    entity_fields = {
        "Project": ["name", "code", "tags", "sg_status"],
        "Episode": ["code", "type", "project.name", "sg_status_list", "tags"],
        "Sequence": ["name", "code", "sg_status_list", "tags", "episode"],
        "Shot": ["code", "sg_status_list", "tags", "sg_sequence"],
        "Asset": ["code", "sg_status_list", "tags", ],
        "Version": ["code", "sg_status_list", "tags"],
        "Task": ["content", "step", "sg_status_list", "tags"]
    }

    project =  {
        "Project": sg.find_one(
            "Project",
            filters=[["id", "is", project["id"]]],
            fields=entity_fields.get("Project")
        )
    }
    project["Project"]["children"] = []

    project_episodes = sg.find("Episode", filters=[["project", "is", project]])

    if project_episodes:
        for episode in project_episodes:
            episode.setdefault("children", [])
            sequences_in_episode = sg.find(
                "Sequence",
                filters=[["episode", "is", episode]],
                entity_fields.get("Sequence")
            )

            if sequences_in_episode:
                for sequence in sequences_in_episode:
                    sequence.setdefault("children", [])
                    shots_in_sequence = sg.find(
                        "Shot",
                        filters=[["sg_sequence", "is", sequence]],
                        entity_fields.get("Shot")
                    )

                    if shots_in_sequence:
                        for shot in shots_in_sequence:
                            shot.setdefault("children", sg.find(
                                "Asset",
                                filters=[["sg_shot", "is", shot]],
                                entity_fields.get("Asset")
                            ))

                            sequence["children"].append(shot)
                    episode["children"].append(sequence)
            project["Project"]["children"].append(episode)

    project_sequences = sg.find(
        "Sequence",
        filters=[
            ["project", "is", project],
            ["episode", "is", None]
        ]
    )

    if project_sequences:
        for sequence in project_sequences:
            sequence.setdefault("children", [])
            shots_in_sequence = sg.find(
                "Shot",
                filters=[["sg_sequence", "is", sequence]],
                entity_fields.get("Shot")
            )

            if shots_in_sequence:
                for shot in shots_in_sequence:
                    shot.setdefault("children", sg.find(
                        "Asset",
                        filters=[["sg_shot", "is", shot]],
                        entity_fields.get("Asset")
                    ))

                    sequence["children"].append(shot)
            project["children"].append(sequence)

    project_shots = sg.find(
        "Shot",
        filters=[
            ["project", "is", project],
            ["episode", "is", None],
            ["sg_sequence", "is", None]
        ]
    )

    if project_shots:
        for shot in shots_in_sequence:
            shot.setdefault("children", sg.find(
                "Asset",
                filters=[["sg_shot", "is", shot]],
                entity_fields.get("Asset")
            ))

            project["children"].append(shot)


def get_shotgrid_hierarchy(sg, project):
    
    entity_fields = {
        "Project": ["name", "code", "tags", "sg_status"],
        "Episode": ["code", "type", "project.name", "sg_status_list", "tags"],
        "Sequence": ["name", "code", "sg_status_list", "tags"],
        "Shot": ["code", "sg_status_list", "tags"],
        "Asset": ["code", "sg_status_list", "tags"],
        "Version": ["code", "sg_status_list", "tags"],
        "Task": ["content", "step", "sg_status_list", "tags"]
    }

    project_dict = {
        "Project": sg.find_one(
            "Project",
            filters=[["id", "is", project["id"]]],
            fields=entity_fields.get("Project")
        )
    }

    for entity in get_shotgrid_project_entities(sg, project):
        children = sg.find(
            entity,
            filters=[["project", "is", project]],
            fields=entity_fields.get(entity)
        )
        project_dict.setdefault(entity, children)

    # Here we should have
    # {
    #     "Project": {},
    #     "Episode": [<list of episodes>], if any
    #     "Sequence": [<list of sequences>], if any
    #     "Shot": [<list of shots>], if any
    #     ...
    # }

    hierarchical_project = project_dict["Project"]
    level = "Project"
    if project_dict.get("Episode"):
        # There are episodes
        hierarchical_project.setdefault("children", project_)
        
        



def get_shotgrid_hierarchy(shotgrid_session: shotgun_api3.Shotgun, project_id: int) -> dict:
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


def get_shotgrid_project_entities(sg, shotgun_project):
    sg_project = sg.find_one("Project", filters=[["id", "is", shotgun_project["id"]]])

    if not sg_project:
        return

    sg_project_schema = sg.schema_entity_read(project_entity=sp)

    project_entities = []

    for entity in AYON_SHOTGRID_ENTITY_MAP:
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

