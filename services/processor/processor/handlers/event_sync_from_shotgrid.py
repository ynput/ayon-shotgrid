"""
Ensure that the project has all the required things in both Ayon and Shotgrid,
mostly Custom Attributes.
"""
from nxtools import logging

REGISTER_EVENT_TYPE = [
    "Shotgun_Sequence_Edit",
    "Shotgun_Shot_Edit",
    "Shotgun_Asset_Edit",
    "Shotgun_Version_Edit",
    "Shotgun_Task_Edit",
]


# TODO: Mapping of all Shotgrid -> Ayon entities that we care

SG_AYON_MAP = {
    "Episode": {
        "entity": "folder",
        "folder_type": "Episode",
        "attrib": {
            "_": "frameEnd",
            "_": "handleStart",
            "_": "clipIn",
            "_": "frameStart",
            "_": "clipOut",
            "_fps": "fps",
            "_testList": "testList",
            "_handleEnd": "handleEnd",
            "_resolutionWidth": "resolutionWidth",
            "id": "shotgridId",
            "_path": "shotgridPath",
            "_resolutionHeight": "resolutionHeight",
            "_pixelAspect": "pixelAspect",
        }
    },
    "Sequence": "folder",
    "Shot": "folder",
    "Asset": "asset",
    "Version": "version",
    "Task": "task",
}

SG_AYON_ENTITY_ATTRIBUTES_MAP = {
    
}

# TODO: Mapping of all the entiteis attributes that we care


def process_event(payload):
    """Entry point of the processor"""
    if not payload:
        logging.error("The Even payload is empty!")
        raise InputError
    
    """
        {
          "id": "670f8af6a7ad11eda0a87ae8710998c5",
          "hash": "482479",
          "topic": "shotgrid.leech",
          "sender": "pine64-pinebookpro",
          "project": null,
          "user": "shotgrid_service",
          "dependsOn": null,
          "status": "finished",
          "retries": 0,
          "description": "Leeched Shotgun_Sequence_Change by Ayon Ynput",
          "summary": {},
          "payload": {
            "id": 482479,
            "meta": {
              "type": "attribute_change",
              "entity_id": 23,
              "new_value": "bunny_010",
              "old_value": "bunny_0102",
              "entity_type": "Sequence",
              "attribute_name": "code",
              "field_data_type": "text"
            },
            "type": "EventLogEntry",
            "user": {
              "id": 88,
              "name": "Ayon Ynput",
              "type": "HumanUser"
            },
            "entity": {
              "id": 23,
              "name": "bunny_010",
              "type": "Sequence"
            },
            "project": {
              "id": 70,
              "name": "Demo: Animation",
              "type": "Project"
            },
            "created_at": "2023-02-08T12:37:41+00:00",
            "event_type": "Shotgun_Sequence_Change",
            "session_uuid": "4f1590c6-a7ad-11ed-b28e-0242ac110003",
            "attribute_name": "code"
          },
          "createdAt": 1675859871.861787,
          "updatedAt": 1675859871.861787
        }
    """
    """
        AYON-SHOTGRID MAPPING
        from ayon_server.entities.folder import FolderEntity
        from ayon_server.entities.project import ProjectEntity
        from ayon_server.entities.representation import RepresentationEntity
        from ayon_server.entities.subset import SubsetEntity
        from ayon_server.entities.task import TaskEntity
        from ayon_server.entities.user import UserEntity
        from ayon_server.entities.version import VersionEntity
        from ayon_server.entities.workfile import WorkfileEntity
        
        
    """
    if "project" not in payload:
        logging.error("The Payload doesn't contain any project, can't proceed!")

    ayon_project = ayon_api.get_project(payload["project"]["name"])

    if not ayon_project:
        logging.error(
            "Unable to find the Ayon Project that corresponds to the Shotgrid Project."
            "Have you set up the project by running 'Create project in Ayon'?"
        )
        raise ValueError
    else:
        if ayon_project["ownAttrib"].get("shotgridId") != payload["project"]["id"]:
            logging.error(
                "Project is missing Shotgun ID attribute, aborting."
            )
            raise ValueError

    ayon_folder = None
    for folder in ayon_api.get_folders(
        ayon_project["name"],
        folder_names=[payload["entity"]["name"]]
    ):
        if folder["folderType"] == payload["entity"]["type"]:
            ayon_folder = folder
    
    if not ayon_folder:
        # TODO: Create this endpoint in `ayon_api`
        ayon_folder = ayon_api.create_folder(
            payload["entity"]["name"],
            ayon_project["name"],
            folder_type=payload["entity"]["type"],
            folder_path=
        )
    

    # TODO: Create this endpoint in `ayon_api`
    ayon_api.update_folder(
        ayon_folder["id"],
        name=payload["meta"]["new_value"]
    )
     
    
    
    # Get entity ID fro Shotgrid payload
    # Check if it exist in ayon
    # If not on ayone, create it
    # 
    


