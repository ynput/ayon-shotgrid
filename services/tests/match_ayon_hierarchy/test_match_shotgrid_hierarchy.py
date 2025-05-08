""" Test match an AYON hierarchy to SG.
"""
import mock
import os
import pytest

import ayon_api

from pytest_ayon.plugin import empty_project  # noqa: F401

from ayon_shotgrid_hub import AyonShotgridHub
import validate
import utils


_IS_GITHUB_ACTIONS = bool(os.getenv("GITHUB_ACTIONS"))


def recursive_partial_assert(expected, actual):
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"Expected dict, got {type(actual)}"
        for key, value in expected.items():
            assert key in actual

        return any(recursive_partial_assert(value, actual[key]) for key, value in expected.items())

    elif isinstance(expected, list):
        assert isinstance(actual, list)

        for exp_item in expected:
            return any(recursive_partial_assert(exp_item, act_item) for act_item in actual)

    return expected == actual


@pytest.mark.skipif(_IS_GITHUB_ACTIONS, reason="WIP make it run on GitHub actions.")
@pytest.mark.parametrize("empty_project", [{"task_types": ("edit")}], indirect=True)
def test_match_hierarchy(empty_project, mockgun_project):    # noqa: F811

    ay_project_data = empty_project
    mg, _ = mockgun_project

    enabled_entities = {
        "Episode": "project",
        "Sequence": "episode",
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
    sg_edit_step = mg.create(
        "Step",
        {
            "code": "edit",
            "entity_type": "Shot",
            "short_name": "edit",
        }
    )

    sg_asset = mg.create(
        "Asset",
        {
            "project": sg_project,
            "code": "my_asset",
        }
    )
    sg_episode = mg.create(
        "Episode",
        {
            "project": sg_project,
            "code": "my_episode",
        }
    )
    sg_sequence = mg.create(
        "Sequence",
        {
            "project": sg_project,
            "episode": sg_episode,
            "code": "my_sequence",
        }
    )

    sg_shot =  mg.create(
        "Shot",
        {
            "project": sg_project,
            "sg_sequence": sg_sequence,
            "code": "my_shot",
        }
    )
    sg_tasks = mg.create(
        "Task",
        {
            "project": sg_project,
            "entity": sg_shot,
            "step": sg_edit_step,
            "content": "my_task",
        }
    )

    # create some data in AYON
    hub = AyonShotgridHub(
        mg,
        ay_project_data.project_name,
        ay_project_data.project_code,
        sg_project_code_field="code",
        sg_enabled_entities=enabled_entities.keys(),
    )

    entity_hub = hub.entity_hub

    # Launch hierarchy sync
    with (
        mock.patch.object(validate, "get_sg_project_enabled_entities", return_value=enabled_entities.items()),
        mock.patch.object(utils, "get_sg_project_enabled_entities", return_value=enabled_entities.items()),
    ):
        hub.synchronize_projects(source="shotgrid")

    # Checks
    project_name = ay_project_data.project_name
    project_children = entity_hub.project_entity.children
    asset_folder = ayon_api.get_folder_by_name(project_name, "my_asset")
    episode_folder = ayon_api.get_folder_by_name(project_name, "my_episode")
    sequence_folder = ayon_api.get_folder_by_name(project_name, "my_sequence")
    shot_folder = ayon_api.get_folder_by_name(project_name, "my_shot")

    # Check asset
    asset_attribs = asset_folder["attrib"]
    assert (
        (str(sg_asset["id"]), "Asset")
        == (asset_attribs["shotgridId"], asset_attribs["shotgridType"])
    )

    # Check episode
    ep_attribs = episode_folder["attrib"]
    assert (
        (str(sg_episode["id"]), "Episode")
        == (ep_attribs["shotgridId"], ep_attribs["shotgridType"])
    )

    # Check sequence
    seq_attribs = sequence_folder["attrib"]
    assert (
        (str(sg_sequence["id"]), "Sequence")
        == (seq_attribs["shotgridId"], seq_attribs["shotgridType"])
    )

    # Check shot
    shot_attribs = shot_folder["attrib"]
    assert (
        (str(sg_shot["id"]), "Shot")
        == (shot_attribs["shotgridId"], shot_attribs["shotgridType"])
    )

    # Check hierarchy
    hierarchy = ayon_api.get_folders_hierarchy(project_name)
    expected = {
        'hierarchy': [
            {
                'children': None,
                'folderType': 'Asset',
                'name': 'my_asset',
            },
            {
                'children': [
                    {
                        'children': [
                            {
                                'children': None,
                                'folderType': 'Shot',
                                'name': 'my_shot',
                            }
                        ],
                        'folderType': 'Sequence',
                        'name': 'my_sequence',
                    }
                ],
                'folderType': 'Episode',
                'name': 'my_episode',
            }
        ],
        'projectName': project_name
    }

    hierarchy_ok = recursive_partial_assert(expected, hierarchy)
    assert hierarchy_ok is True
