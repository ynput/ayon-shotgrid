""" Test match an AYON hierarchy to SG.
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
def test_match_hierarchy_create(empty_project, mockgun_project):    # noqa: F811
    """ Ensure new AYON folders and task are created from an AYON hierarchy.
    """

    ay_project_data = empty_project
    mg, _ = mockgun_project
    hub, sg_project = helpers.setup_sg_project_and_hub(ay_project_data, mg)

    entity_hub = hub.entity_hub

    ay_asset = entity_hub.add_new_folder(
        folder_type="Asset",
        name="my_asset",
        label="my_asset",
        parent_id=entity_hub.project_entity.id,
    )
    ay_sequence = entity_hub.add_new_folder(
        folder_type="Sequence",
        name="my_sequence",
        label="my_sequence",
        parent_id=entity_hub.project_entity.id,
    )
    ay_shot = entity_hub.add_new_folder(
        folder_type="Shot",
        name="my_shot",
        label="my_shot",
        parent_id=ay_sequence.id,
    )
    rendering_task = entity_hub.add_new_task(
        task_type="rendering",
        name="my_rendering_task",
        label="my_rendering_task",
        parent_id=ay_asset.id,
    )
    edit_task = entity_hub.add_new_task(
        task_type="edit",
        name="my_edit_task",
        label="my_edit_task",
        parent_id=ay_shot.id,
    )

    # Launch hierarchy sync
    with (
        mock.patch.object(validate, "get_sg_project_enabled_entities", return_value=helpers.ENABLED_ENTITIES.items()),
        mock.patch.object(utils, "get_sg_project_enabled_entities", return_value=helpers.ENABLED_ENTITIES.items()),
    ):
        hub.synchronize_projects()

    # Checks
    assets = mg.find("Asset", [["project", "is", sg_project]], ["project", "code", "sg_ayon_id"])
    shots = mg.find("Shot", [["project", "is", sg_project]], ["project", "sg_sequence", "code", "sg_ayon_id"])
    sequences = mg.find("Sequence", [["project", "is", sg_project]], ["project", "code", "sg_ayon_id"])
    tasks = mg.find("Task", [["project", "is", sg_project]], ["project", "content", "step.Step.code", "entity", "sg_ayon_id"])

    assert assets == [
        {
            'code': 'my_asset',
            'id': 1,
            'project': {
                'id': 2,
                'name': ay_project_data.project_name,
                'type': 'Project'
            },
            'type': 'Asset',
            'sg_ayon_id': ay_asset.id,
        }
    ]

    assert sequences == [
        {
            'code': 'my_sequence',
            'id': 1,
            'project': {
                'id': 2,
                'name': ay_project_data.project_name,
                'type': 'Project'
            },
            'type': 'Sequence',
            'sg_ayon_id': ay_sequence.id,
        }
    ]
    assert shots == [
        {
            'code': 'my_shot',
            'id': 1,
            'project': {
                'id': 2,
                'name': ay_project_data.project_name,
                'type': 'Project'
            },
            'sg_sequence': {
                'id': 1,
                'type': 'Sequence'
            },
            'type': 'Shot',
            'sg_ayon_id': ay_shot.id
        }
    ]
    assert tasks == [
        {
            'content': 'my_rendering_task',
            'entity': {'id': 1, 'type': 'Asset'},
            'id': 1,
            'project': {
                'id': 2,
                'name': ay_project_data.project_name,
                'type': 'Project'
            },
            'step.Step.code': 'rendering',
            'type': 'Task',
            'sg_ayon_id': rendering_task.id
        },
        {
            'content': 'my_edit_task',
            'entity': {'id': 1, 'type': 'Shot'},
            'id': 2,
            'project': {
                'id': 2,
                'name': ay_project_data.project_name,
                'type': 'Project'
            },
            'step.Step.code': 'edit',
            'type': 'Task',
            'sg_ayon_id': edit_task.id
        }
    ]


@pytest.mark.skipif(helpers.IS_GITHUB_ACTIONS, reason="WIP make it run on GitHub actions.")
@pytest.mark.parametrize("empty_project", [{"task_types": ("rendering", "edit")}], indirect=True)
def test_match_hierarchy_create_version(empty_project, mockgun_project):    # noqa: F811
    """ Ensure new AYON version are created properly.
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
    edit_task = entity_hub.add_new_task(
        task_type="edit",
        name="my_edit_task",
        label="my_edit_task",
        parent_id=ay_shot.id,
    )
    ay_product = entity_hub.add_new_product(
        "product_name",
        "render",
        folder_id=ay_shot.id,
    )
    ay_version = entity_hub.add_new_version(
        25,
        product_id=ay_product.id,
        task_id=edit_task.id,
        data={}
    )
    entity_hub.commit_changes()

    # Launch hierarchy sync
    with (
        mock.patch.object(validate, "get_sg_project_enabled_entities", return_value=helpers.ENABLED_ENTITIES.items()),
        mock.patch.object(utils, "get_sg_project_enabled_entities", return_value=helpers.ENABLED_ENTITIES.items()),
    ):
        hub.synchronize_projects()

    # Checks
    versions = mg.find(
        "Version",
        [["project", "is", sg_project]],
        ["code", "sg_first_frame", "sg_last_frame", "sg_version_type", "sg_ayon_id"]
    )

    assert versions == [
        {
            'code': 'product_name_v025',
            'sg_first_frame': 0,
            'sg_version_type': 'render',
            'id': 1,
            'sg_last_frame': 0,
            'type': 'Version',
            'sg_ayon_id': ay_version.id,
        }
    ]


@pytest.mark.skipif(helpers.IS_GITHUB_ACTIONS, reason="WIP make it run on GitHub actions.")
def test_match_heavy_hierarchy(empty_project, mockgun_project):    # noqa: F811
    """ Ensure syncing 20 assets takes less than 1 second.
    """
    ay_project_data = empty_project
    mg, _ = mockgun_project
    hub, sg_project = helpers.setup_sg_project_and_hub(ay_project_data, mg)

    entity_hub = hub.entity_hub

    for idx in range(20):
        ay_asset = entity_hub.add_new_folder(
            folder_type="Asset",
            name=f"my_asset_{idx}",
            parent_id=entity_hub.project_entity.id,
        )

    # Launch hierarchy sync
    with (
        mock.patch.object(validate, "get_sg_project_enabled_entities", return_value=helpers.ENABLED_ENTITIES.items()),
        mock.patch.object(utils, "get_sg_project_enabled_entities", return_value=helpers.ENABLED_ENTITIES.items()),
    ):
        before = datetime.datetime.now()
        hub.synchronize_projects()
        after = datetime.datetime.now()

    # Checks
    assets = mg.find("Asset", [["project", "is", sg_project]], ["project", "code", "sg_ayon_id"])
    elapsed = after - before

    assert elapsed.total_seconds() <= 1.0
    assert len(assets) == 20
