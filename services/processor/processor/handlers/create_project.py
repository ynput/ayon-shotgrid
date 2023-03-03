"""
Ensure that the project has all the required things in both Ayon and Shotgrid,
custom attributes, tasks types and statuses.
"""
from processor.lib.constants import (
    AYON_SHOTGRID_ATTRIBUTES_MAP,
    AYON_SHOTGRID_ENTITY_MAP,
    SHOTGRID_PROJECT_ATTRIBUTES
)
from processor.lib.utils import (
    get_shotgrid_project_by_name, get_shotgrid_statuses, get_shotgrid_tasks
)

import ayon_api
from nxtools import logging


REGISTER_EVENT_TYPE = ["create-project"]


def process_event(shotgrid_session, payload):
    """Entry point of the processor"""
    if not payload:
        logging.error("The Even payload is empty!")
        raise ValueError

    shotgrid_project = get_shotgrid_project_by_name(
        shotgrid_session,
        payload["project"]
    )

    if not shotgrid_project:
        logging.error(f"Could not find {payload['project']} in Shotgrid!")
        raise ValueError

    project_name = payload["project"]["name"].replace(" ", "_")
    # We can only create projects that start with lowercase
    project_name = f"{project_name[0].lower()}{project_name[1:]}"

    project_code = payload.get("project", {}).get("code", project_name[:3])
    ayon_project = ayon_api.get_project(project_name)

    if not ayon_project:
        # create ayon project
        try:
            ayon_project = ayon_api.create_project(project_name, project_code)
        except Exception as e:
            logging.error("Unable to create new project in Ayon.")
            logging.error(e)

    _create_ayon_entities_attributes(shotgrid_session, ayon_project)
    _create_ayon_project_attributes(
        shotgrid_project,
        shotgrid_session,
        ayon_project
    )

    ayon_api.update_project_tasks(
        ayon_project,
        get_shotgrid_tasks(shotgrid_session, shotgrid_project),
        remove_existing=True
    )
    ayon_api.update_project_statuses(
        ayon_project,
        get_shotgrid_statuses(shotgrid_session, shotgrid_project),
        remove_existing=True
    )


def _create_ayon_project_attributes(
    shotgrid_project: dict,
    shotgrid_session,
    ayon_project: dict
):
    """Create Ayon Project Attributes in Shotgrid

    This will create Project Unique attributes into Shotgrid.
    """
    for attribute, attribute_values in SHOTGRID_PROJECT_ATTRIBUTES.items():
        sg_field_name = attribute_values["name"]
        sg_field_code = attribute_values["sg_field"]
        sg_field_type = attribute_values["type"]
        attribute_exists = False

        try:
            attribute_exists = shotgrid_session.schema_field_read(
                "Project",
                field_name=f"{sg_field_code}"
            )
        except Exception:
            # shotgun_api3.shotgun.Fault: API schema_field_read()
            logging.debug(
                f"Ayon Attribute {sg_field_code} does not exists."
            )

        if not attribute_exists:
            logging.debug(f"Creating {sg_field_code} for Projects.")

            if sg_field_type == "checkbox":
                shotgrid_session.schema_field_create(
                    "Project",
                    sg_field_type,
                    sg_field_name,
                    properties={"default_value": False},
                )
            else:
                shotgrid_session.schema_field_create(
                    "Project",
                    sg_field_type,
                    sg_field_name,
                )


def _create_ayon_entities_attributes(
    shotgrid_session,
    ayon_project: dict
):
    """Create Ayon Project Attributes in Shotgrid"""

    for sg_entity, ayon_entity in AYON_SHOTGRID_ENTITY_MAP.items():
        for attr, attr_definition in ayon_api.get_attribute_for_types(
            ayon_entity
        ):
            properties = {"description": f"Ayon {attr}"}

            field_type = AYON_SHOTGRID_ATTRIBUTES_MAP.get(
                attr_definition["type"], {}
            ).get("name")

            if not field_type:
                logging.warning(
                    f"Field type {attr_definition['type']} not recognized."
                )
                continue

            shotgrid_session.schema_field_create(
                sg_entity,
                field_type,
                f"Ayon {attr}",
                properties
            )

        shotgrid_session.schema_field_create(
            sg_entity,
            "list",
            "Ayon Sync Status",
            {
                "name": "Ayon Sync Status",
                "description": "The Syncronization status against Ayon server.",
                "valid_values": ["Synced", "Failed", "Skipped"],
            }
        )
        # TODO: Somehow change permissions based on the ayon permissions
        # TODO: Somehow change permissions based on the ayon permissions
