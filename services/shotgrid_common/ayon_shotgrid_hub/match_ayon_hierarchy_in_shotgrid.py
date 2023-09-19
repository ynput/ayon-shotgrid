import collections

from constants import (
    CUST_FIELD_CODE_ID,
    CUST_FIELD_CODE_SYNC,
    SHOTGRID_ID_ATTRIB,
    SHOTGRID_TYPE_ATTRIB,
)

from utils import get_sg_entities

from nxtools import logging, log_traceback


def match_ayon_hierarchy_in_shotgrid(entity_hub, sg_project, sg_session):
    """Replicate an AYON project into Shotgrid.

    This function creates a "deck" which we keep increasing while traversing
    the AYON project and finding new children, this is more efficient than
    creating a dictionary with the whole AYON project structure since we
    `popleft` the elements when procesing them.

    Args:
        entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        sg_project (dict): The Shotgrid project.
        sg_session (shotgun_api3.Shotgun): The Shotgrid session.
    """
    logging.info("Getting AYON entities.")
    entity_hub.query_entities_from_server()

    logging.info("Getting Shotgrid entities.")
    sg_entities_by_id, sg_entities_by_parent_id = get_sg_entities(
        sg_session,
        sg_project
    )

    ay_entities_deck = collections.deque()
    sg_project_sync_status = "Synced"

    # Append the project's direct children.
    for ay_project_child in entity_hub._entities_by_parent_id[entity_hub.project_name]:
        ay_entities_deck.append((sg_project, ay_project_child))

    while ay_entities_deck:
        (sg_parent_entity, ay_entity) = ay_entities_deck.popleft()
        logging.debug(f"Processing {ay_entity})")

        sg_entity = None
        if (
            (ay_entity.entity_type == "folder" and ay_entity.folder_type != "Folder")
            or ay_entity.entity_type == "task"
        ):
            sg_entity_id = ay_entity.attribs.get(SHOTGRID_ID_ATTRIB, None)

            if sg_entity_id:
                sg_entity_id = int(sg_entity_id)

                if sg_entity_id in sg_entities_by_id:
                    sg_entity = sg_entities_by_id[sg_entity_id]
                    logging.info(f"Entity already exists in Shotgrid {sg_entity}")

                    if sg_entity[CUST_FIELD_CODE_ID] != ay_entity.id:
                        logging.error("Shotgrid record for AYON id does not match...")
                        try:
                            sg_session.update(
                                sg_entity["shotgridType"],
                                sg_entity["shotgridId"],
                                {
                                    CUST_FIELD_CODE_ID: "",
                                    CUST_FIELD_CODE_SYNC: "Failed"
                                }
                            )
                        except Exception as e:
                            log_traceback(e)
                            sg_project_sync_status = "Failed"

            if sg_entity is None:
                sg_entity = _create_new_entity(
                    ay_entity,
                    sg_session,
                    sg_project,
                    sg_parent_entity
                )
                sg_entities_by_id[sg_entity["id"]] = sg_entity
                sg_entities_by_parent_id[sg_parent_entity["id"]].append(sg_entity)

            ay_entity.attribs.set(
                SHOTGRID_ID_ATTRIB,
                sg_entity["id"]
            )
            ay_entity.attribs.set(
                SHOTGRID_TYPE_ATTRIB,
                sg_entity["type"]
            )
            entity_hub.commit_changes()

        if sg_entity is None:
            # Shotgrid doesn't have the concept of "Folders"
            sg_entity = sg_parent_entity

        for ay_entity_child in entity_hub._entities_by_parent_id.get(ay_entity.id, []):
            ay_entities_deck.append((sg_entity, ay_entity_child))

    sg_session.update(
        "Project",
        sg_project["id"],
        {
            CUST_FIELD_CODE_ID: entity_hub.project_name,
            CUST_FIELD_CODE_SYNC: sg_project_sync_status
        }
    )

def _create_new_entity(ay_entity, sg_session, sg_project, sg_parent_entity):
    """Helper method to create entities in Shotgrid.

    Args:
        parent_entity: Ayon parent entity.
        ay_entity (dict): Shotgrid entity to create.
    """

    if ay_entity.entity_type == "task":
        new_entity = sg_session.create(
            "Task",
            {
                "project": sg_project,
                "content": ay_entity.name,
                CUST_FIELD_CODE_ID: ay_entity.id,
                CUST_FIELD_CODE_SYNC: "Synced",
                "entity": sg_parent_entity,
            }
        )
    else:
        sg_parent_field = sg_parent_entity["type"].lower()
        new_entity = sg_session.create(
            ay_entity.folder_type,
            {
                "code": ay_entity.name,
                CUST_FIELD_CODE_ID: ay_entity.id,
                CUST_FIELD_CODE_SYNC: "Synced",
                sg_parent_field: sg_parent_entity,
            }
        )

    logging.debug(f"Created new entity: {new_entity}")
    logging.debug(f"Parent is: {sg_parent_entity}")
    return new_entity


