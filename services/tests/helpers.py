""" Automated tests helpers.
"""
import os
import dataclasses

from shotgun_api3.lib import mockgun

from ayon_shotgrid_hub import AyonShotgridHub

import constants


IS_GITHUB_ACTIONS = bool(os.getenv("GITHUB_ACTIONS"))
ENABLED_ENTITIES = {
    "Episode": "project",
    "Sequence": "project",
    "Shot": "sg_sequence",
    "Asset": "project",
    "Version": "entity",
    "Task": "entity",
}


def recursive_partial_assert(expected: dict, actual: dict) -> bool:
    """ Partial assert recursive, to compare API result from Mockgun with expected data.
    """
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"Expected dict, got {type(actual)}"
        for key, value in expected.items():
            assert key in actual

        return all(recursive_partial_assert(value, actual[key]) for key, value in expected.items())

    elif isinstance(expected, list):
        assert isinstance(actual, list)

        for exp_item in expected:
            return any(recursive_partial_assert(exp_item, act_item) for act_item in actual)

    return expected == actual


def setup_sg_project_and_hub(
        ay_project_data: dataclasses.dataclass,
        mg: mockgun.Shotgun
    ) -> AyonShotgridHub:
    """ Utils setup SG project and hub objects.
    """
    # create SG project and step in Mockgun
    sg_project = mg.create(
        "Project",
        {
            "code": ay_project_data.project_code,
            "name": ay_project_data.project_name,
            "sg_ayon_auto_sync": True,
        }
    )
    mg.create("Step", {"code": "edit", "entity_type": "Asset"})
    mg.create("Step", {"code": "edit", "entity_type": "Shot"})
    mg.create("Step", {"code": "rendering", "entity_type": "Asset"})
    mg.create("Step", {"code": "rendering", "entity_type": "Shot"})

    # create some data in AYON
    hub = AyonShotgridHub(
        mg,
        ay_project_data.project_name,
        ay_project_data.project_code,
        sg_project_code_field="code",
        sg_enabled_entities=ENABLED_ENTITIES.keys(),
    )

    hub.entity_hub.project_entity.attribs[constants.SHOTGRID_TYPE_ATTRIB] = "Project"
    hub.entity_hub.project_entity.attribs[constants.SHOTGRID_ID_ATTRIB] = sg_project["id"]
    hub.entity_hub.commit_changes()

    return hub, sg_project
