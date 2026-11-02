""" Test conversion of SG date fields to AYON datetime attributes.

SG date fields have no timezone and are returned as "YYYY-MM-DD" strings.
They must be stored in AYON as midnight UTC, whatever the timezone of the
machine running the service.
"""
import datetime
import time

import mock
import pytest

from ayon_api.utils import entity_data_json_default

import constants
import utils


DATETIME_SCHEMA = {
    "attributes": [
        {"name": "endDate", "data": {"type": "datetime"}},
        {"name": "startDate", "data": {"type": "datetime"}},
    ]
}


class FakeAttribs(dict):

    def set(self, key, value):
        self[key] = value


class FakeEntity:

    entity_type = "task"
    label = None

    def __init__(self, attribs=None):
        self.attribs = FakeAttribs(attribs or {})

    def get_name(self):
        return "compositing"


def _sent_to_server(value):
    """Return the UTC instant `ayon_api` sends to the server on commit."""
    timestamp = entity_data_json_default(value)
    return datetime.datetime.fromtimestamp(
        timestamp, datetime.timezone.utc
    ).isoformat()


@pytest.fixture
def prague_timezone(monkeypatch):
    """Run the test as if the service machine was in Europe/Prague."""
    if not hasattr(time, "tzset"):
        pytest.skip("time.tzset() is not available on this platform.")

    monkeypatch.setenv("TZ", "Europe/Prague")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


@pytest.fixture
def datetime_schema():
    with mock.patch.object(
        utils.ayon_api, "get_attributes_schema", return_value=DATETIME_SCHEMA
    ):
        yield


def _update_end_date(entity, sg_value):
    utils.update_ay_entity_custom_attributes(
        entity,
        {"type": "task", "label": None, "attribs": {"endDate": sg_value}},
        {"endDate": "due_date"},
    )


def test_naive_date_shifts_with_local_timezone(prague_timezone):
    """Document the issue: a naive midnight is serialized in local time."""
    naive = datetime.datetime(2026, 9, 3)
    assert _sent_to_server(naive) == "2026-09-02T22:00:00+00:00"


def test_update_stores_sg_date_as_utc_midnight(datetime_schema):
    entity = FakeEntity()
    _update_end_date(entity, "2026-09-03")

    value = entity.attribs["endDate"]
    assert value == datetime.datetime(
        2026, 9, 3, tzinfo=datetime.timezone.utc
    )
    assert _sent_to_server(value) == "2026-09-03T00:00:00+00:00"


def test_update_does_not_shift_date_in_other_timezone(
    prague_timezone, datetime_schema
):
    entity = FakeEntity()
    _update_end_date(entity, "2026-09-03")

    assert _sent_to_server(entity.attribs["endDate"]) == (
        "2026-09-03T00:00:00+00:00"
    )


def test_update_fixes_previously_shifted_date(datetime_schema):
    entity = FakeEntity({"endDate": "2026-09-02T22:00:00+00:00"})
    _update_end_date(entity, "2026-09-03")

    assert _sent_to_server(entity.attribs["endDate"]) == (
        "2026-09-03T00:00:00+00:00"
    )


def test_update_keeps_same_date(datetime_schema):
    current_value = "2026-09-03T00:00:00+00:00"
    entity = FakeEntity({"endDate": current_value})
    _update_end_date(entity, "2026-09-03")

    assert entity.attribs["endDate"] == current_value


def test_create_stores_sg_date_as_utc_midnight(datetime_schema):
    sg_datetime = datetime.datetime(
        2026, 9, 3, 10, 30,
        tzinfo=datetime.timezone(datetime.timedelta(hours=2))
    )
    sg_ay_dict = {
        "type": "task",
        "task_type": "edit",
        "name": "compositing",
        "label": "Compositing",
        "attribs": {
            constants.SHOTGRID_ID_ATTRIB: 7184,
            constants.SHOTGRID_TYPE_ATTRIB: "Task",
            "endDate": "2026-09-03",
            # SG date/time fields are returned as datetime objects.
            "startDate": sg_datetime,
        },
        "data": {constants.CUST_FIELD_CODE_ID: None},
    }
    entity_hub = mock.MagicMock()
    parent_entity = mock.MagicMock(entity_type="folder", id="parent_id")

    utils.create_new_ayon_entity(
        mock.MagicMock(), entity_hub, parent_entity, sg_ay_dict
    )

    attribs = entity_hub.add_new_task.call_args.kwargs["attribs"]
    assert _sent_to_server(attribs["endDate"]) == "2026-09-03T00:00:00+00:00"
    assert attribs["startDate"] is sg_datetime
