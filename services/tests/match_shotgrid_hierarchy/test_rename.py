""" Test renaming through label when matchin hierarchy.
"""
import mock
import pytest

import ayon_api

from pytest_ayon.plugin import empty_project  # noqa: F401

from ayon_shotgrid_hub import AyonShotgridHub
import validate
import utils

from .. import helpers


@pytest.mark.skipif(helpers.IS_GITHUB_ACTIONS, reason="WIP make it run on GitHub actions.")
def test_label_renamed(empty_project, mockgun_project):    # noqa: F811

    ay_project_data = empty_project
    mg, _ = mockgun_project

    # create SG project and step in Mockgun
    sg_project = mg.create(
        "Project",
        {
            "code": ay_project_data.project_code,
            "name": ay_project_data.project_name,
            "sg_ayon_auto_sync": False,
        }
    )
    mg.create(
        "Asset",
        {
            "project": sg_project,
            "code": "my_asset",
        }
    )

    # create some data in AYON
    hub = AyonShotgridHub(
        mg,
        ay_project_data.project_name,
        ay_project_data.project_code,
        sg_project_code_field="code",
        sg_enabled_entities=helpers.ENABLED_ENTITIES.keys(),
    )

    # Launch hierarchy sync
    with (
        mock.patch.object(validate, "get_sg_project_enabled_entities", return_value=helpers.ENABLED_ENTITIES.items()),
        mock.patch.object(utils, "get_sg_project_enabled_entities", return_value=helpers.ENABLED_ENTITIES.items()),
    ):
        hub.synchronize_projects(source="shotgrid")

    mg.update("Asset", 1, {"code": "my_asset (renamed)"})

    # React to sg event.
    with (
        mock.patch.object(validate, "get_sg_project_enabled_entities", return_value=helpers.ENABLED_ENTITIES.items()),
        mock.patch.object(utils, "get_sg_project_enabled_entities", return_value=helpers.ENABLED_ENTITIES.items()),
    ):
        hub.synchronize_projects(source="shotgrid")

    asset_folder = ayon_api.get_folder_by_name(ay_project_data.project_name, "my_asset")

    assert asset_folder["name"] == "my_asset"
    assert asset_folder["label"] == "my_asset (renamed)"
