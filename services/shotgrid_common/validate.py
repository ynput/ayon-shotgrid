""" Validation
"""
import collections

import ayon_api
from ayon_api.entity_hub import EntityHub


import constants
from utils import get_logger, get_sg_project_enabled_entities


def check_project_disabled_entities(
        ay_project,
        sg_project,
        enabled_entities,
        sg_session,
    ):
    """ Ensure enabled SG entities are compatibles for a given project.
    """
    disabled_entities = []
    ay_entities = [
        folder["name"]
        for folder in ay_project.project_entity.folder_types
        if folder["name"] in enabled_entities
    ]

    sg_entities = [
        entity_name
        for entity_name, _ in get_sg_project_enabled_entities(
            sg_session,
            sg_project,
            enabled_entities
        )
    ]

    disabled_entities = [
        ay_entity
        for ay_entity in ay_entities
        if ay_entity not in sg_entities
    ]

    if disabled_entities:
        # This must be done manually and cannot be changed from the API yet.
        # https://community.shotgridsoftware.com/t/set-project-configuration-via-python/15416
        return (
            f"Unable to sync project {sg_project}, you need "
            f"to manually enable the following entities in Shotgrid: {disabled_entities}. "
            "This is done via Project > Project Actions > Tracking Settings."
        )

    return None


def _validate_project_statuses_mapping(
        ay_project,
        sg_project,
        enabled_entities,
        sg_session,
        log
    ):
    """ Check statuses are compatibles between SG and AYON
        for a a specific project.
    """
    # Ayon statuses
    ay_project_entity =  EntityHub(ay_project["name"])
    ay_project_statuses = [
        status for status in ay_project_entity.project_entity.statuses
    ]

    # SG statuses for entities/folder
    for entity in enabled_entities:
        try:
            status_data = sg_session.schema_field_read(
                entity, project_entity=sg_project,
            )["sg_status_list"]["properties"]

        except KeyError:
            log.debug("Entity %s does not support statuses in SG.", entity)
            continue

        statuses = status_data["valid_values"]["value"]
        disabled_statuses = status_data["hidden_values"]["value"]
        sg_statuses = [
            status for status in statuses
            if statuses not in disabled_statuses
        ]

        entity_type = (
            entity.lower()
            if entity in ("Version", "Note", "Task") else "folder"
        )

        syncable_statuses = []
        for ay_status in ay_project_statuses:
            if entity_type not in ay_status.get_scope():
                continue

            for sg_status in sg_statuses:
                if ay_status.short_name == sg_status:
                    syncable_statuses.append(sg_status)

        if syncable_statuses:
            log.debug(
                "Only %r statuses will be synced for %s.%s "
                "every other statuses will be ignored.",
                syncable_statuses,
                ay_project["name"],
                entity,
            )
        else:
            log.warning(
                "No common statuses set between SG and AYON for %s.%s",
                ay_project["name"],
                entity,
            )


def validate_projects_sync(
        sg_session,
        enabled_entities,
        log=None
    ):
    """ Validate overhall project configuration.
    """
    log = log or get_logger(__file__)
    errors = []

    all_ay_projects = ayon_api.get_projects()

    for ay_project in all_ay_projects:
        if not ay_project["attrib"].get(constants.SHOTGRID_ID_ATTRIB):
            log.debug(
                "AY Project %s is not set up to sync with SG.",
                ay_project["name"]
            )
            continue

        sg_project_id = int(ay_project["attrib"][constants.SHOTGRID_ID_ATTRIB])
        sg_project = sg_session.find_one(
            "Project",
            [["id", "is", sg_project_id]],
            fields=["code", "name", "sg_ayon_auto_sync"],
        )

        if not sg_project:
            log.warning(
                "AY Project %s is supposed to sync with SG. "
                "However associated project cannot be found in SG (id: %s)",
                ay_project["name"],
                sg_project_id
            )
            continue

        error = check_project_disabled_entities(
            EntityHub(ay_project["name"]),
            sg_project,
            enabled_entities,
            sg_session,
        )

        if error:
            errors.append(error)
            continue

        # Check statuses compatibility
        error = _validate_project_statuses_mapping(
            ay_project,
            sg_project,
            enabled_entities,
            sg_session,
            log,
        )

        if error:
            errors.append(error)
            continue

        # Autosync
        if sg_project["sg_ayon_auto_sync"] and ay_project["attrib"]["shotgridPush"]:
            log.debug(
                "AY Project %s is properly setup to sync with SG project %s automatically.",
                ay_project["name"],
                sg_project["code"],
            )

        elif sg_project["sg_ayon_auto_sync"]:
            log.debug(
                "AY Project %s will received updates from SG project %s automatically, "
                "but it will not push anything back. Enable 'shotgunPush' attribute "
                "of the AY project to enabled that.",
                ay_project["name"],
                sg_project["code"],
            )

        elif ay_project["attrib"]["shotgridPush"]:
            log.debug(
                "AY Project %s will send updates to SG project %s automatically, "
                "but it will not pull anything back. Enable 'sg_ayon_auto_sync' field "
                "of the SG project to enabled that.",
                ay_project["name"],
                sg_project["code"],
            )

        else:
            log.debug(
                "AY Project %s is not setup to push or receive updates "
                "from/to SG project %s automatically. Sync must be triggered manually.",
                ay_project["name"],
                sg_project["code"],
            )

    if errors:
        errors.insert(0, "Project setup validation failed:")
        raise ValueError("\n".join(errors))


def validate_custom_attribs_map(
        sg_session,
        custom_attribs_map,
        log=None
    ):
    """
    """
    log = log or get_logger(__file__)
    errors = []
    sg_schemas = {}
    ay_schemas = {}

    AY_SG_TYPE_MAPPING = {
        "number": "integer",
        "float": "float",
        "text": "string",
        "date_time": "datetime",
        "date": "datetime",
    }

    all_mapped_sgs = [entry["sg"] for entry in custom_attribs_map]
    all_mapped_ays = [entry["ayon"] for entry in custom_attribs_map]

    duplicate_sgs = [
        item for item, count in collections.Counter(all_mapped_sgs).items()
        if item and count > 1
    ]
    duplicate_ays = [
        item for item, count in collections.Counter(all_mapped_ays).items()
        if item and count > 1
    ]

    if duplicate_ays:
        errors.append(f"Found duplicate settings for AYON attribute(s): {duplicate_ays}.")

    if duplicate_sgs:
        errors.append(f"Found duplicate settings for SG field(s): {duplicate_sgs}.")

    for entry in custom_attribs_map:

        if not entry["sg"]:
            log.debug(
                "AYON attribute %r will not be mapped to SG "
                "(no 'sg' field set) for entities %r.",
                entry["ayon"],
                entry["scope"],
            )
            continue

        if not entry["scope"]:
            log.debug(
                "AYON attribute %r will not be mapped to SG "
                "(empty scope)", entry["ayon"]
            )
            continue

        # Ensure that the mapped field exist for each scope
        # in both AYON and SG with specified type.
        for scope in entry["scope"]:

            if scope not in sg_schemas:
                sg_schemas[scope] = sg_session.schema_field_read(scope)

            fields_options = (f'{entry["sg"]}', f'sg_{entry["sg"]}')
            for field_attempt in fields_options:
                if field_attempt in list(sg_schemas[scope]):
                    field_schema = sg_schemas[scope][field_attempt]

                    if not field_schema["editable"]["value"]:
                        errors.append(
                            f"SG field {scope}.{field_attempt} "
                            "is set as non-editable."
                        )

                    conformed_field_type = AY_SG_TYPE_MAPPING.get(
                        field_schema["data_type"]["value"],
                        "unknown"
                    )

                    if conformed_field_type != entry["type"]:
                        errors.append(
                            f"SG field {scope}.{field_attempt} is of invalid type. "
                            f'Expected "{entry["type"]}"" got "{conformed_field_type}".'
                        )

                    break

            else:
                # TODO investigate this.
                errors.append(
                    f'SG field {entry["sg"]} does not exists for {scope}.'
                )

    if errors:
        errors.insert(0, "Settings validation failed:")
        raise ValueError("\n".join(errors))
