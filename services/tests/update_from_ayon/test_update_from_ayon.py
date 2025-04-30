""" Test entity update from AYON to SG.
"""
import mock

import ayon_api
from ayon_api.entity_hub import EntityHub, FolderEntity, TaskEntity

import constants

from ..test_sg_base import hub_and_project, mockgun_project


def test_update_folder(hub_and_project):
    mg = hub_and_project["mg"]
    project = hub_and_project["project"]
    hub = hub_and_project["hub"]
    entity_hub = hub_and_project["entity_hub"]

    sg_shot = mg.create("Shot", {
        "project": project,
        "code": "my_shot"
    })

    ay_event = {
        'topic': 'entity.folder.attrib_changed',
        'project': 'test_project',
        'payload': {
            'oldValue': {'resolutionWidth': 1920},
            'newValue': {'resolutionWidth': 250},
        },
        'summary': {
            'entityId': 'dummy',
            'parentId': 'dummy_parent'
        },
        'user': 'admin'
    }

    shot_entity = FolderEntity(
        "my_shot",
        "Shot",
        parent_id=None,
        entity_hub=entity_hub,
        attribs={
            constants.SHOTGRID_ID_ATTRIB: str(sg_shot["id"]),
            constants.SHOTGRID_TYPE_ATTRIB: "Shot",
        }
    )

    hub.custom_attribs_map = {"resolutionWidth": "sg_resolution_width"}

    with mock.patch.object(EntityHub, "get_or_query_entity_by_id", return_value=shot_entity):
        hub.react_to_ayon_event(ay_event)

    result = mg.find("Shot", [["project", "is", project]], ["sg_resolution_width"])[0]
    assert result == {'id': 1, 'type': 'Shot', 'sg_resolution_width': 250}


def test_update_folder_status(hub_and_project):
    mg = hub_and_project["mg"]
    project = hub_and_project["project"]
    hub = hub_and_project["hub"]
    entity_hub = hub_and_project["entity_hub"]

    sg_shot = mg.create("Shot", {
        "project": project,
        "code": "my_shot",
        "sg_status_list": "ip"
    })

    ay_event = {
        'topic': 'entity.folder.status_changed',
        'project': 'test_project',
        'payload': {
            'oldValue': 'Waiting to Start',
            'newValue': 'Final'
        },
        'summary': {
            'entityId': 'dummy',
            'parentId': 'dummy_parent'
        },
        'user': 'admin'
    }

    shot_entity = FolderEntity(
        "my_shot",
        "Shot",
        parent_id=None,
        entity_hub=entity_hub,
        attribs={
            constants.SHOTGRID_ID_ATTRIB: str(sg_shot["id"]),
            constants.SHOTGRID_TYPE_ATTRIB: "Shot",
        }
    )

    with mock.patch.object(EntityHub, "get_or_query_entity_by_id", return_value=shot_entity):
        hub.react_to_ayon_event(ay_event)

    result = mg.find("Shot", [["project", "is", project]], ["sg_status_list"])[0]
    assert result == {'id': 1, 'type': 'Shot', 'sg_status_list': 'fin'}


def test_update_task_status(hub_and_project):
    mg = hub_and_project["mg"]
    project = hub_and_project["project"]
    hub = hub_and_project["hub"]
    entity_hub = hub_and_project["entity_hub"]

    sg_shot = mg.create("Shot", {"project": project, "code": "shot01"})
    step = mg.create("Step", {"code": "edit", "entity_type": "Shot"})
    sg_task = mg.create("Task", {
        "project": project,
        "entity": sg_shot,
        "step": step,
        "sg_status_list": "ip",
    })

    ay_event = {
        'topic': 'entity.task.status_changed',
        'project': 'test_project',
        'payload': {'newValue': 'Final', 'oldValue': 'In Progress'},
        'summary': {'entityId': 'dummy', 'parentId': 'parent'},
        'user': 'admin'
    }

    task_entity = TaskEntity(
        "edit_task",
        "edit",
        folder_id="parent",
        entity_id="dummy",
        entity_hub=entity_hub,
        attribs={
            constants.SHOTGRID_ID_ATTRIB: str(sg_task["id"]),
            constants.SHOTGRID_TYPE_ATTRIB: "Task"
        }
    )

    with mock.patch.object(EntityHub, "get_or_query_entity_by_id", return_value=task_entity):
        hub.react_to_ayon_event(ay_event)

    result = mg.find("Task", [["project", "is", project]], ["sg_status_list", "step"])[0]
    assert result == {
        "id": 1,
        "type": "Task",
        "sg_status_list": "fin",
        "step": {"id": step["id"], "type": "Step"}
    }


def test_task_assignee_update(hub_and_project):
    mg = hub_and_project["mg"]
    project = hub_and_project["project"]
    hub = hub_and_project["hub"]
    entity_hub = hub_and_project["entity_hub"]

    step = mg.create("Step", {"code": "edit", "entity_type": "Shot"})
    sg_task = mg.create("Task", {"project": project, "step": step})
    sg_user = mg.create("HumanUser", {"login": "test_user@email.com", "name": "test_user"})

    ay_event = {
        'topic': 'entity.task.assignees_changed',
        'project': 'test_project',
        'payload': {'oldValue': [], 'newValue': ['test_user']},
        'summary': {'entityId': 'dummy', 'parentId': 'parent'},
        'user': 'admin'
    }

    task_entity = TaskEntity(
        "edit_task",
        "edit",
        folder_id="parent",
        entity_id="dummy",
        entity_hub=entity_hub,
        attribs={
            constants.SHOTGRID_ID_ATTRIB: str(sg_task["id"]),
            constants.SHOTGRID_TYPE_ATTRIB: "Task"
        }
    )

    with mock.patch.object(EntityHub, "get_or_query_entity_by_id", return_value=task_entity), \
         mock.patch.object(ayon_api, "get_user", return_value={'name': 'test_user', 'data': {'sg_user_id': sg_user["id"]}}):
        hub.react_to_ayon_event(ay_event)

    result = mg.find("Task", [["project", "is", project]], ["task_assignees"])[0]
    assert result == {
        "id": 1,
        "type": "Task",
        "task_assignees": [{"id": sg_user["id"], "type": "HumanUser"}]
    }


def test_task_invalid_assignee_update(hub_and_project):
    mg = hub_and_project["mg"]
    project = hub_and_project["project"]
    hub = hub_and_project["hub"]
    entity_hub = hub_and_project["entity_hub"]

    step = mg.create("Step", {"code": "edit", "entity_type": "Shot"})
    sg_task = mg.create("Task", {"project": project, "step": step})

    ay_event = {
        'topic': 'entity.task.assignees_changed',
        'project': 'test_project',
        'payload': {'oldValue': [], 'newValue': ['missing_user']},
        'summary': {'entityId': 'dummy', 'parentId': 'parent'},
        'user': 'admin'
    }

    task_entity = TaskEntity(
        "edit_task",
        "edit",
        folder_id="parent",
        entity_id="dummy",
        entity_hub=entity_hub,
        attribs={
            constants.SHOTGRID_ID_ATTRIB: str(sg_task["id"]),
            constants.SHOTGRID_TYPE_ATTRIB: "Task"
        }
    )

    with mock.patch.object(EntityHub, "get_or_query_entity_by_id", return_value=task_entity), \
         mock.patch.object(ayon_api, "get_user", return_value={'name': 'missing_user'}):
        hub.react_to_ayon_event(ay_event)

    result = mg.find("Task", [["project", "is", project]], ["task_assignees"])[0]
    assert result == {
        "id": 1,
        "type": "Task",
        "task_assignees": []
    }
