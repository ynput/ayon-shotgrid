""" Test update AYON hierarchy to SG.
"""
import mock
import os
import pytest
import datetime

from pytest_ayon.plugin import empty_project  # noqa: F401

from ayon_shotgrid_hub import AyonShotgridHub
import constants
import validate
import utils

from .. import helpers


@pytest.mark.skipif(helpers.IS_GITHUB_ACTIONS, reason="WIP make it run on GitHub actions.")
@pytest.mark.parametrize("empty_project", [{"task_types": ("rendering", "edit")}], indirect=True)
def test_match_hierarchy_update(empty_project, mockgun_project):    # noqa: F811
    """ Ensure new Flow entities are updated from an AYON hierarchy.
    """
    ay_project_data = empty_project
    mg, _ = mockgun_project
    hub, sg_project = helpers.setup_sg_project_and_hub(ay_project_data, mg)

    entity_hub = hub.entity_hub

    # Add "final" status
    data = entity_hub.project_entity.statuses.to_data()
    data.append({"name": "Final", "shortName": "fin"})
    data.append({"name": "In Progress", "shortName": "ip"})
    entity_hub.project_entity.set_statuses(data)

    # An asset that exist in SG but needs update.
    ay_asset = entity_hub.add_new_folder(
        folder_type="Asset",
        name="my_asset",
        label="my_asset",
        parent_id=entity_hub.project_entity.id,
        status="Final",
        attribs={
            constants.SHOTGRID_ID_ATTRIB: "1",
            constants.SHOTGRID_TYPE_ATTRIB: "Asset"
        }
    )
    edit_task = entity_hub.add_new_task(
        task_type="edit",
        name="my_edit_task",
        label="my_edit_task",
        parent_id=ay_asset.id,
        status="Final",
        attribs={
            constants.SHOTGRID_ID_ATTRIB: "1",
            constants.SHOTGRID_TYPE_ATTRIB: "Task"
        }
    )

    sg_asset = mg.create(
        "Asset",
        {
            "code": "my_asset",
            "sg_ayon_id": ay_asset.id,
            "sg_status_list": "wtg",
            "project": sg_project,
        }
    )
    mg.create(
        "Task",
        {
            'content': 'my_edit_task',
            'entity': sg_asset,
            'project': sg_project,
            'sg_ayon_id': edit_task.id,
            "sg_status_list": "wtg",
        }
    )

    # A sequence that does not exist in SG but needs update.
    ay_sequence = entity_hub.add_new_folder(
        folder_type="Sequence",
        name="my_sequence",
        label="my_sequence",
        status="Final",
        parent_id=entity_hub.project_entity.id,
    )
    entity_hub.commit_changes()

    # Launch hierarchy sync
    with (
        mock.patch.object(validate, "get_sg_project_enabled_entities", return_value=helpers.ENABLED_ENTITIES.items()),
        mock.patch.object(utils, "get_sg_project_enabled_entities", return_value=helpers.ENABLED_ENTITIES.items()),
    ):
        hub.synchronize_projects()

    sg_asset = mg.find_one(
        "Asset",
        [["id", "is", 1]],
        ["sg_status_list"]
    )
    sg_sequence = mg.find_one(
        "Sequence",
        [["id", "is", 1]],
        ["sg_status_list", "sg_ayon_id"],
    )
    sg_task = mg.find_one(
        "Task",
        [["id", "is", 1]],
        ["sg_status_list"]
    )

    # Ensure asset status got updated.
    assert sg_asset["sg_status_list"] == "fin"

    # Ensure sequence got created and updated.
    assert sg_sequence["sg_ayon_id"] == ay_sequence.id
    assert sg_sequence["sg_status_list"] == "fin"

    # Ensure task status got updated.
    assert sg_task["sg_status_list"] == "fin"


@pytest.mark.skipif(helpers.IS_GITHUB_ACTIONS, reason="WIP make it run on GitHub actions.")
def test_update_create_folder(empty_project, mockgun_project):    # noqa: F811
    """ Ensure updating a folder that does not exist yet in SG, creates it.
    """
    ay_project_data = empty_project
    mg, _ = mockgun_project
    hub, sg_project = helpers.setup_sg_project_and_hub(ay_project_data, mg)

    entity_hub = hub.entity_hub

    ay_shot = entity_hub.add_new_folder(
        folder_type="Shot",
        name="my_shot",
        label="my_shot",
    )

    # Add "final" status
    data = entity_hub.project_entity.statuses.to_data()
    data.append({"name": "Final", "shortName": "fin"})
    entity_hub.project_entity.set_statuses(data)
    entity_hub.commit_changes()

    ay_event = {
        'topic': 'entity.folder.status_changed',
        'project': 'test_project',
        'payload': {
            'oldValue': 'not_started',
            'newValue': 'Final'
        },
        'summary': {
            'entityId': ay_shot.id,
            'parentId': ay_shot.parent.id
        },
        'user': 'admin'
    }

    with (
        mock.patch.object(validate, "get_sg_project_enabled_entities", return_value=helpers.ENABLED_ENTITIES.items()),
        mock.patch.object(utils, "get_sg_project_enabled_entities", return_value=helpers.ENABLED_ENTITIES.items()),
    ):
        hub.react_to_ayon_event(ay_event)

    result = mg.find_one("Shot", [["project", "is", sg_project]], ["sg_ayon_id"])
    assert result["sg_ayon_id"] == ay_shot.id
