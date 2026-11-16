""" Test entity update from SG to AYON.

A SG change event should only update the AYON attribute matching
the changed SG field, and leave the other attributes untouched.
"""
import mock
import pytest

from ayon_shotgrid_hub import update_from_shotgrid

import constants


CUSTOM_ATTRIBS_MAP = {
    "resolutionWidth": "resolution_width",
    "fps": "sg_fps",
}


class FakeAttribs(dict):

    def set(self, key, value):
        self[key] = value


class FakeEntity:

    id = "ayon_shot_id"
    entity_type = "folder"
    label = "my_shot"
    immutable_for_hierarchy = False

    def __init__(self, attribs):
        self.attribs = FakeAttribs(attribs)
        self.name = "my_shot"

    def get_name(self):
        return self.name


@pytest.fixture
def ay_entity():
    # AYON values differ from the SG ones for every mapped attribute.
    return FakeEntity({
        constants.SHOTGRID_ID_ATTRIB: "1",
        constants.SHOTGRID_TYPE_ATTRIB: "Shot",
        "resolutionWidth": 1920,
        "fps": 25.0,
    })


def _update_from_sg_event(ay_entity, attribute_name):
    sg_event = {
        "entity_type": "Shot",
        "entity_id": 1,
        "attribute_name": attribute_name,
    }
    sg_ay_dict = {
        "type": "folder",
        "label": "my_shot",
        "attribs": {
            constants.SHOTGRID_ID_ATTRIB: 1,
            constants.SHOTGRID_TYPE_ATTRIB: "Shot",
            "resolutionWidth": 250,
            "fps": 24.0,
        },
        "data": {constants.CUST_FIELD_CODE_ID: ay_entity.id},
    }
    entity_hub = mock.MagicMock()
    entity_hub.get_or_query_entity_by_id.return_value = ay_entity

    with mock.patch.object(
        update_from_shotgrid,
        "get_sg_entity_as_ay_dict",
        return_value=sg_ay_dict,
    ):
        update_from_shotgrid.update_ayon_entity_from_sg_event(
            sg_event,
            {"id": 1, "type": "Project"},
            mock.MagicMock(),
            entity_hub,
            ["Shot"],
            "code",
            {"compatibility_settings": {"default_task_type": "Generic"}},
            custom_attribs_map=CUSTOM_ATTRIBS_MAP,
        )


@pytest.mark.parametrize("attribute_name", ["resolution_width", "sg_resolution_width"])
def test_update_only_changed_attribute(ay_entity, attribute_name):
    _update_from_sg_event(ay_entity, attribute_name)

    assert ay_entity.attribs["resolutionWidth"] == 250
    assert ay_entity.attribs["fps"] == 25.0


def test_update_unmapped_field_keeps_attributes(ay_entity):
    _update_from_sg_event(ay_entity, "description")

    assert ay_entity.attribs["resolutionWidth"] == 1920
    assert ay_entity.attribs["fps"] == 25.0
