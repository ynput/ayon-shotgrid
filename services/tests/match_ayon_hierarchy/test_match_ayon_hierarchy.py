""" Test match an AYON hierarchy to SG.
"""
import mock
import os
import pytest

# TODO enable this
#from pytest_ayon.plugin import empty_project  # noqa: F401

from ayon_shotgrid_hub import AyonShotgridHub
import validate
import utils


_IS_GITHUB_ACTIONS = bool(os.getenv("GITHUB_ACTIONS"))


# TODO make this run via Docker service.
os.environ["AYON_SERVER_URL"] = "http://localhost:5000"
os.environ["AYON_API_KEY"] = "cf8d512ad405457b801a6804d4bf5368"


#@pytest.mark.skipif(_IS_GITHUB_ACTIONS, reason="WIP make it run on GitHub actions.")
@pytest.mark.parametrize("empty_project", [{"task_types": ("rendering", "edit")}], indirect=True)
def test_match_hierarchy(empty_project, mockgun_project):    # noqa: F811

    ay_project_data = empty_project
    mg, _ = mockgun_project

    enabled_entities = {
        "Episode": "project",
        "Sequence": "project",
        "Shot": "sg_sequence",
        "Asset": "project",
        "Version": "entity"
    }

    # create SG project and step in Mockgun
    sg_project = mg.create(
        "Project",
        {
            "code": ay_project_data.project_code,
            "name": ay_project_data.project_name,
            "sg_ayon_auto_sync": False,
        }
    )
    mg.create("Step", {"code": "edit", "entity_type": "Shot"})
    mg.create("Step", {"code": "rendering", "entity_type": "Asset"})

    # create some data in AYON
    hub = AyonShotgridHub(
        mg,
        ay_project_data.project_name,
        ay_project_data.project_code,
        sg_project_code_field="code",
        sg_enabled_entities=enabled_entities.keys(),
    )

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
        mock.patch.object(validate, "get_sg_project_enabled_entities", return_value=enabled_entities.items()),
        mock.patch.object(utils, "get_sg_project_enabled_entities", return_value=enabled_entities.items()),
    ):
        hub.synchronize_projects()

    # Checks
    assets = mg.find("Asset", [["project", "is", sg_project]], ["project", "code", "sg_ayon_id"])
    shots = mg.find("Shot", [["project", "is", sg_project]], ["project", "sg_sequence", "code", "sg_ayon_id"])
    sequences = mg.find("Sequence", [["project", "is", sg_project]], ["project", "code", "sg_ayon_id"])
    tasks = mg.find("Task", [["project", "is", sg_project]], ["project", "code", "step.Step.code", "entity", "sg_ayon_id"])

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
            'code': None,
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
            'code': None,
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

    print("OK")
