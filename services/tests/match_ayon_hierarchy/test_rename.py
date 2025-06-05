""" Test match an AYON hierarchy to SG.
"""
import mock
import pytest


from pytest_ayon.plugin import empty_project  # noqa: F401

import validate
import utils

from .. import helpers


@pytest.mark.skipif(helpers.IS_GITHUB_ACTIONS, reason="WIP make it run on GitHub actions.")
def test_update_rename_folder(empty_project, mockgun_project):    # noqa: F811
    """ Ensure renaming an entity in Flow renamed the AYON label.
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
    ay_rendering_task = entity_hub.add_new_task(
        task_type="rendering",
        name="my_rendering_task",
        label="my_rendering_task",
        parent_id=ay_shot.id,
    )
    entity_hub.commit_changes()

    # Sync once to create matching entities in SG
    with (
        mock.patch.object(validate, "get_sg_project_enabled_entities", return_value=helpers.ENABLED_ENTITIES.items()),
        mock.patch.object(utils, "get_sg_project_enabled_entities", return_value=helpers.ENABLED_ENTITIES.items()),
    ):
        hub.synchronize_projects()

    # Rename label for shot and task
    ay_shot.label = "my_shot (renamed)"
    ay_rendering_task.label = "my_rendering_task (renamed)"
    entity_hub.commit_changes()

    # Sync another time to sync new labels.
    with (
        mock.patch.object(validate, "get_sg_project_enabled_entities", return_value=helpers.ENABLED_ENTITIES.items()),
        mock.patch.object(utils, "get_sg_project_enabled_entities", return_value=helpers.ENABLED_ENTITIES.items()),
    ):
        hub.synchronize_projects()

    sg_shot = mg.find_one("Shot", [["project", "is", sg_project]], ["code", "sg_ayon_id"])
    sg_task = mg.find_one("Task", [["project", "is", sg_project]], ["content", "sg_ayon_id"])

    assert sg_shot == {
        'sg_ayon_id': ay_shot.id,
        'type': 'Shot',
        'id': 1,
        'code': 'my_shot (renamed)'
    }

    assert sg_task == {
        'sg_ayon_id': ay_rendering_task.id,
        'type': 'Task',
        'content': 'my_rendering_task (renamed)',
        'id': 1
    }
