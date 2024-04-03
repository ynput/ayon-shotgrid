import collections

from constants import (
    CUST_FIELD_CODE_ID,
    CUST_FIELD_CODE_SYNC,
    SHOTGRID_ID_ATTRIB,
    SHOTGRID_TYPE_ATTRIB,
)

from utils import (
    get_sg_entities,
    get_sg_entity_parent_field,
    get_sg_entity_as_ay_dict,
    get_sg_custom_attributes_data
)

from nxtools import logging, log_traceback


def match_ayon_hierarchy_in_shotgrid(
    entity_hub,
    sg_project,
    sg_session,
    sg_enabled_entities,
    project_code_field,
    custom_attribs_map,
):
    """Replicate an AYON project into Shotgrid.

    This function creates a "deck" which we keep increasing while traversing
    the AYON project and finding new children, this is more efficient than
    creating a dictionary with the whole AYON project structure since we
    `popleft` the elements when processing them.

    Args:
        entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        sg_project (dict): The Shotgrid project.
        sg_session (shotgun_api3.Shotgun): The Shotgrid session.
        project_code_field (str): The Shotgrid project code field.
    """
    logging.info("Getting AYON entities.")
    entity_hub.query_entities_from_server()

    logging.info("Getting Shotgrid entities.")
    sg_ay_dicts, sg_ay_dicts_parents = get_sg_entities(
        sg_session,
        sg_project,
        sg_enabled_entities,
        project_code_field,
        custom_attribs_map,
    )

    sg_ay_dicts_deck = collections.deque()

    # Append the project's direct children.
    for sg_ay_dict_child in entity_hub._entities_by_parent_id[entity_hub.project_name]:
        sg_ay_dicts_deck.append((
            get_sg_entity_as_ay_dict(
                sg_session, "Project", sg_project["id"], project_code_field,
                custom_attribs_map=custom_attribs_map
            ),
            sg_ay_dict_child
        ))

    ay_project_sync_status = "Synced"

    while sg_ay_dicts_deck:
        (sg_ay_parent_entity, ay_entity) = sg_ay_dicts_deck.popleft()
        logging.debug(f"Processing {ay_entity})")

        sg_ay_dict = None

        if (
            (ay_entity.entity_type == "folder" and ay_entity.folder_type != "Folder")
            or ay_entity.entity_type == "task"
        ):
            sg_entity_id = ay_entity.attribs.get(SHOTGRID_ID_ATTRIB, None)
            sg_entity_type = ay_entity.attribs.get(SHOTGRID_TYPE_ATTRIB, "")

            if sg_entity_type == "AssetCategory":
                continue

            if sg_entity_id in sg_ay_dicts:
                sg_ay_dict = sg_ay_dicts[sg_entity_id]
                logging.info(f"Entity already exists in Shotgrid {sg_ay_dict}")

                if sg_ay_dict["data"][CUST_FIELD_CODE_ID] != ay_entity.id:
                    logging.error("Shotgrid record for AYON id does not match...")
                    try:
                        sg_session.update(
                            sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB],
                            sg_ay_dict["attribs"][SHOTGRID_ID_ATTRIB],
                            {
                                CUST_FIELD_CODE_ID: "",
                                CUST_FIELD_CODE_SYNC: "Failed"
                            }
                        )
                    except Exception as e:
                        log_traceback(e)
                        ay_project_sync_status = "Failed"
                else:
                    # Update SG entity custom attributes with AYON data
                    data_to_update = get_sg_custom_attributes_data(
                        sg_session,
                        ay_entity.attribs.to_dict(),
                        sg_entity_type,
                        custom_attribs_map
                    )
                    if data_to_update:
                        logging.info("Syncing custom attributes on entity.")
                        sg_session.update(
                            sg_entity_type,
                            sg_entity_id,
                            data_to_update
                        )

            if sg_ay_dict is None:
                sg_parent_entity = sg_session.find_one(
                    sg_ay_parent_entity["attribs"][SHOTGRID_TYPE_ATTRIB],
                    filters=[["id", "is", sg_ay_parent_entity["attribs"][SHOTGRID_ID_ATTRIB]]]
                )
                sg_ay_dict = _create_new_entity(
                    ay_entity,
                    sg_session,
                    sg_project,
                    sg_parent_entity,
                    sg_enabled_entities,
                    project_code_field,
                    custom_attribs_map,
                )
                sg_entity_id = sg_ay_dict["attribs"][SHOTGRID_ID_ATTRIB]
                sg_ay_dicts[sg_entity_id] = sg_ay_dict
                sg_ay_dicts_parents[sg_parent_entity["id"]].append(sg_ay_dict)

            ay_entity.attribs.set(
                SHOTGRID_ID_ATTRIB,
                sg_entity_id
            )
            ay_entity.attribs.set(
                SHOTGRID_TYPE_ATTRIB,
                sg_ay_dict["type"]
            )
            entity_hub.commit_changes()

        if sg_ay_dict is None:
            # Shotgrid doesn't have the concept of "Folders"
            sg_ay_dict = sg_ay_parent_entity

        for ay_entity_child in entity_hub._entities_by_parent_id.get(ay_entity.id, []):
            sg_ay_dicts_deck.append((sg_ay_dict, ay_entity_child))
    
    # Sync project attributes from AYON to ShotGrid
    data_to_update = {
        CUST_FIELD_CODE_ID: entity_hub.project_name,
        CUST_FIELD_CODE_SYNC: ay_project_sync_status
    }
    data_to_update.update(get_sg_custom_attributes_data(
        sg_session,
        entity_hub.project_entity.attribs.to_dict(),
        "Project",
        custom_attribs_map
    ))
    sg_session.update(
        "Project",
        sg_project["id"],
        data_to_update
    )

    entity_hub.project_entity.attribs.set(
        SHOTGRID_ID_ATTRIB,
        sg_project["id"]
    )

    entity_hub.project_entity.attribs.set(
        SHOTGRID_TYPE_ATTRIB,
        "Project"
    )


def _create_new_entity(
    ay_entity,
    sg_session,
    sg_project,
    sg_parent_entity,
    sg_enabled_entities,
    project_code_field,
    custom_attribs_map,
):
    """Helper method to create entities in Shotgrid.

    Args:
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
        ay_entity (dict): The AYON entity.
        sg_project (dict): The Shotgrid Project.
        sg_type (str): The Shotgrid type of the new entity.
        sg_enabled_entities (list): List of Shotgrid entities to be enabled.
        project_code_field (str): The Shotgrid project code field.
        custom_attribs_map (dict): Dictionary of extra attributes to store in the SG entity.
    """

    if ay_entity.entity_type == "task":
        step_query_filters = [["code", "is", ay_entity.task_type]]

        if sg_parent_entity["type"] in ["Asset", "Shot", "Episode", "Sequence"]:
            step_query_filters.append(
                ["entity_type", "is", sg_parent_entity["type"]]
            )

        task_step = sg_session.find_one(
            "Step",
            filters=step_query_filters,
        )
        if not task_step:
            raise ValueError(
                f"Unable to create Task {ay_entity.task_type} {ay_entity}\n"
                f"-> Shotgrid is missing Pipeline Step {ay_entity.task_type}"
            )

        sg_type = "Task"
        data = {
            "project": sg_project,
            "content": ay_entity.label,
            CUST_FIELD_CODE_ID: ay_entity.id,
            CUST_FIELD_CODE_SYNC: "Synced",
            "entity": sg_parent_entity,
            "step": task_step,
        }
    else:
        sg_parent_field = get_sg_entity_parent_field(
            sg_session, sg_project, ay_entity.folder_type, sg_enabled_entities)

        sg_type = ay_entity.folder_type
        data = {
            "project": sg_project,
            "code": ay_entity.name,
            CUST_FIELD_CODE_ID: ay_entity.id,
            CUST_FIELD_CODE_SYNC: "Synced",
        }
        # If parent field is different than project, add parent field to
        # data
        # NOTE: why?
        if (sg_parent_field != "project" and sg_parent_entity["type"] != "Project"):
            data[sg_parent_field] = sg_parent_entity

    # Fill up data with any extra attributes from Ayon we want to sync to SG
    data.update(get_sg_custom_attributes_data(
        sg_session,
        ay_entity.attribs.to_dict(),
        sg_type,
        custom_attribs_map
    ))

    try:
        sg_entity = sg_session.create(sg_type, data)
    except Exception as e:
        logging.error(
            f"Unable to create SG entity {sg_type} with data: {data}")
        log_traceback(e)
        raise e
    
    logging.debug(f"Created new entity: {sg_entity}")
    logging.debug(f"Parent is: {sg_parent_entity}")

    sg_ay_dict = get_sg_entity_as_ay_dict(
        sg_session,
        sg_entity["type"],
        sg_entity["id"],
        project_code_field,
        custom_attribs_map=custom_attribs_map
    )
    return sg_ay_dict
