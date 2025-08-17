""" Test entity creation from AYON to SG.
"""
import pytest
from unittest import mock

import ayon_api
from ayon_api.entity_hub import EntityHub, FolderEntity, TaskEntity, VersionEntity, ProductEntity

import constants
import utils


@pytest.fixture
def common_ay_event():
    return {
        'createdAt': '2025-04-29T14:10:34.642408+00:00',
        'dependsOn': None,
        'description': '',
        'hash': 'b7bfe222250311f0ac900242ac120002',
        'id': 'b7bfe222250311f0ac900242ac120002',
        'payload': {},
        'project': 'test_project',
        'retries': 0,
        'sender': '1YWHoUnmujGNUKwXWuiLvP',
        'senderType': 'api',
        'status': 'finished',
        'summary': {'entityId': 'entity_id', 'parentId': None},
        'topic': '',
        'updatedAt': '2025-04-29T14:10:34.642408+00:00',
        'user': 'admin'
    }


def test_create_new_episode(hub_and_project, common_ay_event):
    """ Ensure a new Episode is created in Flow from an AYON event.
    """

    common_ay_event["description"] = "Folder my_new_episode created"
    common_ay_event["topic"] = "entity.folder.created"

    folder_entity = FolderEntity("new_episode", "Episode", parent_id=None, entity_hub=hub_and_project["entity_hub"])

    with mock.patch.object(EntityHub, "get_or_query_entity_by_id", return_value=folder_entity), \
         mock.patch.object(FolderEntity, "parent", new_callable=mock.PropertyMock) as mock_parent, \
         mock.patch.object(utils, "get_sg_entity_parent_field", return_value="project"):

        mock_parent.return_value = hub_and_project["project_entity"]
        hub_and_project["hub"].react_to_ayon_event(common_ay_event)

    new_episode = hub_and_project["mg"].find("Episode", [["project", "is", hub_and_project["project"]]], ["code"])[0]
    assert new_episode == {'code': 'new_episode', 'id': 1, 'type': 'Episode'}


def test_create_new_asset(hub_and_project, common_ay_event):
    """ Ensure a new Asset is created in Flow from an AYON event.
    """

    common_ay_event["description"] = "Folder new_asset created"
    common_ay_event["topic"] = "entity.folder.created"

    folder_entity = FolderEntity("new_asset", "Asset", parent_id=None, entity_hub=hub_and_project["entity_hub"])

    with mock.patch.object(EntityHub, "get_or_query_entity_by_id", return_value=folder_entity), \
         mock.patch.object(FolderEntity, "parent", new_callable=mock.PropertyMock) as mock_parent, \
         mock.patch.object(utils, "get_sg_entity_parent_field", return_value="project"):

        mock_parent.return_value = hub_and_project["project_entity"]
        hub_and_project["hub"].react_to_ayon_event(common_ay_event)

    new_asset = hub_and_project["mg"].find("Asset", [["project", "is", hub_and_project["project"]]], ["code"])[0]
    assert new_asset == {'code': 'new_asset', 'id': 1, 'type': 'Asset'}


def test_create_new_shot(hub_and_project, common_ay_event):
    """ Ensure a new Shot is created in Flow from an AYON event.
    """

    sg_sequence = hub_and_project["mg"].create("Sequence", {"project": hub_and_project["project"], "code": "my_sequence"})
    sequence_entity = FolderEntity(
        "new_sequence",
        "Sequence",
        parent_id=None,
        entity_hub=hub_and_project["entity_hub"],
        attribs={
            constants.SHOTGRID_ID_ATTRIB: str(sg_sequence["id"]),
            constants.SHOTGRID_TYPE_ATTRIB: "Sequence",
        }
    )

    shot_entity = FolderEntity("new_shot", "Shot", parent_id=sequence_entity.id, entity_hub=hub_and_project["entity_hub"])

    common_ay_event["description"] = "Folder new_shot created"
    common_ay_event["topic"] = "entity.folder.created"

    with mock.patch.object(EntityHub, "get_or_query_entity_by_id", return_value=shot_entity), \
         mock.patch.object(FolderEntity, "parent", new_callable=mock.PropertyMock) as mock_parent, \
         mock.patch.object(utils, "get_sg_entity_parent_field", return_value="sg_sequence"):

        mock_parent.return_value = sequence_entity
        hub_and_project["hub"].react_to_ayon_event(common_ay_event)

    new_shot = hub_and_project["mg"].find("Shot", [["project", "is", hub_and_project["project"]]], ["code", "sg_sequence"])[0]
    assert new_shot == {
        'code': 'new_shot',
        'id': 1,
        'type': 'Shot',
        'sg_sequence': {'type': 'Sequence', 'id': 1}
    }


def test_create_new_task(hub_and_project):
    """ Ensure a new Task is created in Flow from an AYON event.
    """

    mg = hub_and_project["mg"]
    project = hub_and_project["project"]
    entity_hub = hub_and_project["entity_hub"]
    hub = hub_and_project["hub"]

    sg_sequence = mg.create("Sequence", {"project": project, "code": "my_sequence"})
    mg.create("Step", {"code": "edit", "entity_type": "Sequence"})

    sequence_entity = FolderEntity(
        "new_sequence",
        "Sequence",
        parent_id=None,
        entity_hub=entity_hub,
        attribs={
            constants.SHOTGRID_ID_ATTRIB: str(sg_sequence["id"]),
            constants.SHOTGRID_TYPE_ATTRIB: "Sequence",
        }
    )

    task_entity = TaskEntity(
        "new_task",
        task_type="edit",
        folder_id="11d9f4cd1fac11f099587cb566e6652d",
        entity_id="f56a1540251011f08eedd9567d7d6404",
        entity_hub=entity_hub,
    )

    ay_event = {
        'createdAt': '2025-04-29T15:45:23.550702+00:00',
        'dependsOn': None,
        'description': 'Task new_edit_task created',
        'hash': 'f69a64a6251011f0ac900242ac120002',
        'id': 'f69a64a6251011f0ac900242ac120002',
        'payload': {},
        'project': 'test_project',
        'retries': 0,
        'sender': '1YWHoUnmujGNUKwXWuiLvP',
        'senderType': 'api',
        'status': 'finished',
        'summary': {
            'entityId': 'f56a1540251011f08eedd9567d7d6404',
            'parentId': '11d9f4cd1fac11f099587cb566e6652d'
        },
        'topic': 'entity.task.created',
        'updatedAt': '2025-04-29T15:45:23.550702+00:00',
        'user': 'admin'
    }

    with mock.patch.object(EntityHub, "get_or_query_entity_by_id", return_value=task_entity), \
         mock.patch.object(TaskEntity, "parent", new_callable=mock.PropertyMock) as mock_parent, \
         mock.patch.object(utils, "get_sg_entity_parent_field", return_value="entity"), \
         mock.patch.object(utils, "_sg_to_ay_dict", return_value={}):

        mock_parent.return_value = sequence_entity
        hub.react_to_ayon_event(ay_event)

    new_task = mg.find("Task", [["project", "is", project]], ["code", "entity", "step"])[0]
    assert new_task == {
        'code': None,
        'entity': {'id': 1, 'type': 'Sequence'},
        'step': {'id': 1, 'type': 'Step'},
        'id': 1,
        'type': 'Task'
    }

def test_create_new_version(hub_and_project):
    """ Ensure a new Task is created in Flow from an AYON event.
    """

    mg = hub_and_project["mg"]
    project = hub_and_project["project"]
    entity_hub = hub_and_project["entity_hub"]
    hub = hub_and_project["hub"]

    sg_sequence = mg.create("Sequence", {"project": project, "code": "my_sequence"})
    mg.create("Step", {"code": "edit", "entity_type": "Sequence"})

    sequence_entity = FolderEntity(
        "new_sequence",
        "Sequence",
        parent_id=project,
        entity_hub=entity_hub,
        attribs={
            constants.SHOTGRID_ID_ATTRIB: str(sg_sequence["id"]),
            constants.SHOTGRID_TYPE_ATTRIB: "Sequence",
        }
    )

    product_entity = ProductEntity(
        "product_name",
        "render",
        folder_id=sequence_entity.id,
        entity_hub=entity_hub,
    )

    version_entity = VersionEntity(
        30,
        product_id=product_entity.id,
        data={},
        entity_hub=entity_hub,
    )

    ay_event = {
        'createdAt': '2025-04-29T15:45:23.550702+00:00',
        'dependsOn': None,
        'description': 'Task new_edit_task created',
        'hash': 'f69a64a6251011f0ac900242ac120002',
        'id': 'f69a64a6251011f0ac900242ac120002',
        'payload': {},
        'project': 'test_project',
        'retries': 0,
        'sender': '1YWHoUnmujGNUKwXWuiLvP',
        'senderType': 'api',
        'status': 'finished',
        'summary': {
            'entityId': 'f56a1540251011f08eedd9567d7d6404',
            'parentId': '11d9f4cd1fac11f099587cb566e6652d'
        },
        'topic': 'entity.version.created',
        'updatedAt': '2025-04-29T15:45:23.550702+00:00',
        'user': 'admin'
    }

    with mock.patch.object(EntityHub, "get_or_query_entity_by_id", return_value=version_entity), \
         mock.patch.object(VersionEntity, "parent", new_callable=mock.PropertyMock) as mock_parent, \
         mock.patch.object(ProductEntity, "parent", new_callable=mock.PropertyMock) as mock_parent_2, \
         mock.patch.object(ayon_api, "get_folder_by_id", return_value=sequence_entity.to_create_body_data()), \
         mock.patch.object(ayon_api, "get_product_by_id", return_value={"productType": "render"}), \
         mock.patch.object(utils, "get_sg_entity_parent_field", return_value="entity"), \

        mock_parent.return_value = product_entity
        mock_parent_2.return_value = sequence_entity
        hub.react_to_ayon_event(ay_event)

    new_version = mg.find_one(
        "Version",
        [["project", "is", project]],
        [
            "code", "entity", "sg_version_type",
            "sg_first_frame", "sg_last_frame"
        ]
    )

    assert new_version == {
        'sg_version_type': 'render',
        'entity': {'type': 'Sequence', 'id': 1},
        'sg_last_frame': 0,
        'code': 'product_name_v030',
        'sg_first_frame': 0,
        'type': 'Version',
        'id': 1
    }
