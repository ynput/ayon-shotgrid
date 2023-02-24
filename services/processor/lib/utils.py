import shotgun_api3

from .constants import AYON_SHOTGRID_ENTITY_MAP, SHOTGRID_PROJECT_ATTRIBUTES


def get_shotgrid_project_hierarchy(sg, project):
    entity_fields = {
        "Project": ["name", "code", "tags", "sg_status"],
        "Episode": ["code", "type", "project.name", "sg_status_list", "tags"],
        "Sequence": ["name", "code", "sg_status_list", "tags", "episode"],
        "Shot": ["name", "code", "sg_status_list", "tags", "sg_sequence"],
        "Asset": ["code", "sg_status_list", "tags", ],
        "Version": ["code", "sg_status_list", "tags"],
        "Task": ["content", "step", "sg_status_list", "tags"]
    }

    sg_project = sg.find_one(
        "Project",
        filters=[["id", "is", project["id"]]],
        fields=entity_fields.get("Project")
    )

    project = {
        "Project": sg_project
    }

    entities_by_id = {}
    entities_by_parent_id = {}

    project["Project"]["children"] = []

    project_episodes = sg.find(
        "Episode",
        filters=[["project", "is", sg_project]],
        fields=entity_fields.get("Episode"))

    if project_episodes:
        for episode in project_episodes:
            episode["parent_id"] = sg_project["id"]

            episode.setdefault("children", [])
            sequences_in_episode = sg.find(
                "Sequence",
                filters=[["episode", "is", episode]],
                fields=entity_fields.get("Sequence")
            )

            if sequences_in_episode:
                for sequence in sequences_in_episode:
                    sequence.setdefault("children", [])
                    shots_in_sequence = sg.find(
                        "Shot",
                        filters=[["sg_sequence", "is", sequence]],
                        fields=entity_fields.get("Shot")
                    )

                    if shots_in_sequence:
                        for shot in shots_in_sequence:
                            shot.setdefault("children", [])
                            assets_in_shot = sg.find(
                                "Asset",
                                filters=[["shots", "name_contains", shot["code"]]],
                                fields=entity_fields.get("Asset")
                            )
                            if assets_in_shot:
                                for asset in assets_in_shot:
                                    entities_by_id[asset["id"]] = asset
                                    entities_by_parent_id.setdefault(shot["id"], [])
                                    entities_by_parent_id[shot["id"]].append(asset)

                                shot["children"] = assets_in_shot

                            entities_by_id[shot["id"]] = shot
                            entities_by_parent_id.setdefault(sequence["id"], [])
                            entities_by_parent_id[sequence["id"]].append(shot)
                            sequence["children"].append(shot)

                    entities_by_id[sequence["id"]] = sequence
                    entities_by_parent_id.setdefault(episode["id"], [])
                    entities_by_parent_id[episode["id"]].append(sequence)
                    episode["children"].append(sequence)

            entities_by_id[episode["id"]] = episode
            entities_by_parent_id.setdefault(sg_project["id"], [])
            entities_by_parent_id[sg_project["id"]].append(episode)
            project["Project"]["children"].append(episode)

    project_sequences = sg.find(
        "Sequence",
        filters=[
            ["project", "is", sg_project],
            ["episode", "is", None]
        ],
        fields=entity_fields.get("Sequence")
    )

    if project_sequences:
        for sequence in project_sequences:
            sequence.setdefault("children", [])
            shots_in_sequence = sg.find(
                "Shot",
                filters=[["sg_sequence", "is", sequence]],
                fields=entity_fields.get("Shot")
            )

            if shots_in_sequence:
                for shot in shots_in_sequence:
                    shot.setdefault("children", [])
                    assets_in_shot = sg.find(
                        "Asset",
                        filters=[["shots", "name_contains", shot["code"]]],
                        fields=entity_fields.get("Asset")
                    )
                    if assets_in_shot:
                        for asset in assets_in_shot:
                            entities_by_id[asset["id"]] = asset
                            entities_by_parent_id.setdefault(shot["id"], [])
                            entities_by_parent_id[shot["id"]].append(asset)

                        shot["children"] = assets_in_shot

                    entities_by_id[shot["id"]] = shot
                    entities_by_parent_id.setdefault(sequence["id"], [])
                    entities_by_parent_id[sequence["id"]].append(shot)
                    sequence["children"].append(shot)

            entities_by_id[sequence["id"]] = sequence
            entities_by_parent_id.setdefault(sg_project["id"], [])
            entities_by_parent_id[sg_project["id"]].append(sequence)
            project["Project"]["children"].append(sequence)

    project_shot_filters = [["project", "is", sg_project]]

    if project_episodes:
        project_shot_filters.append(["episode", "is", None])

    if project_sequences:
        project_shot_filters.append(["sg_sequence", "is", None])

    project_shots = sg.find(
        "Shot",
        filters=project_shot_filters,
        fields=entity_fields.get("Shot")
    )

    if project_shots:
        for shot in shots_in_sequence:
            shot.setdefault("children", [])
            assets_in_shot = sg.find(
                "Asset",
                filters=[["shots", "name_contains", shot["code"]]],
                fields=entity_fields.get("Asset")
            )

            if assets_in_shot:
                for asset in assets_in_shot:
                    entities_by_id[asset["id"]] = asset
                    entities_by_parent_id.setdefault(shot["id"], [])
                    entities_by_parent_id[shot["id"]].append(asset)

                shot["children"] = assets_in_shot

            entities_by_id[shot["id"]] = shot
            entities_by_parent_id.setdefault(sg_project["id"], [])
            entities_by_parent_id[sg_project["id"]].append(shot)
            project["Project"]["children"].append(shot)

    project_assets = sg.find(
        "Asset",
        filters=[["project", "is", sg_project]],
        fields=entity_fields.get("Asset")
    )

    if project_assets:
        for asset in project_assets:
            if asset["id"] not in entities_by_id:
                entities_by_id[asset["id"]] = asset

            entities_by_parent_id.setdefault(sg_project["id"], [])
            if asset not in entities_by_parent_id[sg_project["id"]]:
                entities_by_parent_id[sg_project["id"]].append(asset)
            project["Project"]["children"].append(asset)

    return project, entities_by_id, entities_by_parent_id

def _old_get_shotgrid_hierarchy(shotgrid_session: shotgun_api3.Shotgun, project_id: int) -> dict:
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

