"""
Ensure that the project has all the required things in both Ayon and Shotgrid,
custom attributes, tasks types and statuses.
"""

REGISTER_EVENT_TYPE = ["Shotgun_Project_New"]

def process_event(shotgrid_session, payload):
    """Entry point of the processor"""
    if not payload:
        logging.error("The Even payload is empty!")
        raise InputError

    logging.info(f"Preparing project {} ()")

"""
                "project": {
              "id": 70,
              "name": "Demo: Animation",
              "type": "Project"
            },

"""

    shotgrid_project = shotgrid_session.find_one(
        "Project",
        [["id", "is", payload["project"]["id"]]],
        fields=["code", "id", "sg_status"]
    )

    project_name = payload["project"]["name"].replace(" ", "_")
    # We can only create projects that start with lowercase
    project_name = f"{project_name[0].lower()}{project_name[1:]}"
    project_code = payload["project"]["code"] if payload["project"]["code"] else project_name[:3]

    ayon_project = ayon_api.get_project(project_name)

    if not ayon_project:
        #create ayon project
        try:
            ayon_project = ayon_api.create_project(project_name, project_code)
        except Exception as e:
            logging.error("Unable to create new project in Ayon.")
            logging.error(e)

    _create_ayon_attribs(shotgrid_session, ayon_project)

    _create_shotgrid_tasks(shotgrid_session, ayon_project)


def _create_shotgrid_tasks(shotgrid_session: shotgun_api3.Shotgun, ayon_project: dict):
    """Ensure the Ayon project has all the required Tasks from Shotgird."""
    sg_tasks = []

    for task in shotgrid_session.find(
        "Task",
        [["project", "is", shotgun_project]],
        fields=["content", "step", "sg_status", "tags"]
    ):
        if task["content"] not in unique_tasks:
            unique_tasks.append(task["content"])

    # Create all the Tasks in the project


def _create_shotgrid_statuses(shotgrid_session: shotgun_api3.Shotgun, ayon_project: dict):
    """Ensure the Ayon project has all the required Statuses from Shotgrid."""
    sg_statuses = {}

    # These are the entities that have statuses in SG
    for entity in ["Episode", "Sequence", "Shot", "Asset", "Task"]:
        for status_schema in shotgrid_projectsession.schema_field_read(entity, "sg_status_list"):
            statuses = status_schema["sg_status_list"]["properties"]["display_values"]["value"]
            for short_name, display_name in statuses.items():
                sg_statuses.setdefault(short_name, display_name)

    # Create all statuse in Ayon



def _create_ayon_attributes(shotgrid_session: shotgun_api3.Shotgun, ayon_project: dict):
    """Create Ayon Project Attributes in Shotgrid"""
    
    for attr_key, attr_value in ayon_dict.items():
        properties = {"description": f"Ayon {attr_key}"}

        field_type = type(attr_value).__name__

        if field_type == "list" and attr_value:
            properties = {
                "default_value": {
                    "editable": True,
                    "value": attr_value[0]
                },
                "display_values": {
                    "editable": False,
                    "value": attr_value,
                },
                "hidden_values": {
                    "editable": False,
                    "value": []
                },
                "summary_default": {
                    "editable": True,
                    "value": "status_list"
                },
                "valid_values": {
                    "editable": True,
                    "value": attr_value,
                }
            }

            # This assumes it's a list of dictionaries
            if isinstance(attr_value[0], dict):
                properties.update(
                    "display_values": {
                        "editable": False,
                        "value": {
                            k, v
                            for k, v in attr_value.items()
                        }
                    },
                    "valid_values": {
                        "editable": True,
                        "value": list(attr_value),
                    }
                )

        sg.schema_field_create(
            "Project",
            field_type,
            f"ayon_{attr_key}",
            properties
        )
        


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
                sg_dict["children"][children_index] = sg.nav_expand(children["path"], entity_fields=entity_fields)
                _populate_nested_children(sg_dict["children"][children_index])

                
