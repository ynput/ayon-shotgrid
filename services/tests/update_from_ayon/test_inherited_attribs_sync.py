""" Test AYON inherited attributes are synced to SG.

EntityHub only holds own attribute values, inherited ones are None.
SG has no inheritance, so the values resolved by AYON must be sent,
whatever the sync: manual (update and creation) or event based.

Hierarchy used by all tests, `new` being set on the sequence:

    seq           own value: new
    ├── sh010     inherits             -> new
    │   └── task  inherits from sh010  -> new
    └── sh020     own value: own
        └── task  inherits from sh020  -> own
"""
import mock
import pytest

import ayon_api
from ayon_api.entity_hub import EntityHub, FolderEntity, TaskEntity

from ayon_shotgrid_hub.match_ayon_hierarchy_in_shotgrid import (
    match_ayon_hierarchy_in_shotgrid,
)

import constants
import utils

from . import helpers
from .conftest import MockEntityHub


ADDON_SETTINGS = {"compatibility_settings": {"default_task_type": "Generic"}}
SG_ENABLED_ENTITIES = ["Sequence", "Shot", "Task"]


# (AYON attribute, SG attribute, {state: (AYON value, SG value)})
ATTRIB_CASES = [
    pytest.param(
        "resolutionWidth", "resolution_width",
        {"old": (1920, 1920), "new": (250, 250), "own": (2048, 2048)},
        id="int",
    ),
    pytest.param(
        "fps", "fps",
        {"old": (25.0, 25.0), "new": (24.0, 24.0), "own": (30.0, 30.0)},
        id="float",
    ),
    # Only available on SG Task in the test schema.
    pytest.param(
        "startDate", "start_date",
        {
            "old": ("2026-01-01T00:00:00+00:00", "2026-01-01"),
            "new": ("2026-09-03T00:00:00+00:00", "2026-09-03"),
            "own": ("2026-05-05T00:00:00+00:00", "2026-05-05"),
        },
        id="date",
    ),
]


class MockAttribs(dict):

    def set(self, key, value):
        self[key] = value

    def to_dict(self):
        return dict(self)


class InheritEntityHub(MockEntityHub):

    def __init__(self, project_name, ay_attrib):
        super().__init__(project_name)
        self._ay_attrib = ay_attrib
        self._project_entity.attribs = MockAttribs()
        self._entities_by_parent_id = {project_name: []}

    def get_attributes_for_type(self, _):
        return {
            constants.SHOTGRID_ID_ATTRIB: str,
            constants.SHOTGRID_TYPE_ATTRIB: str,
            self._ay_attrib: None,
        }

    def fetch_hierarchy_entities(self):
        return

    def _add(self, entity, parent_id):
        self._entities_by_parent_id.setdefault(parent_id, []).append(entity)
        return entity


class Scenario:
    """Build the same hierarchy in AYON and optionally in SG."""

    def __init__(self, mg, sg_project, ay_attrib, sg_attrib, values):
        self.mg = mg
        self.sg_project = sg_project
        self.ay_attrib = ay_attrib
        self.custom_attribs_map = {ay_attrib: sg_attrib}
        self.values = values
        self.sg_field = self._get_sg_field(sg_attrib)

        mg.create("Step", {"code": "edit", "entity_type": "Shot"})
        self.entity_hub = InheritEntityHub("test_project", ay_attrib)

        # name: (AYON entity, own state or None, resolved state)
        self.ay_entities = {}
        seq = self._add_folder("seq", "Sequence", "test_project", "new", "new")
        sh010 = self._add_folder("sh010", "Shot", seq.id, None, "new")
        self._add_task("task010", sh010.id, None, "new")
        sh020 = self._add_folder("sh020", "Shot", seq.id, "own", "own")
        self._add_task("task020", sh020.id, None, "own")

        self.sg_entities = {}

    def _get_sg_field(self, sg_attrib):
        schema = self.mg.schema_field_read("Task")
        return sg_attrib if sg_attrib in schema else f"sg_{sg_attrib}"

    def _ay_value(self, state):
        return self.values[state][0] if state else None

    def _add_folder(self, name, folder_type, parent_id, own, resolved):
        folder = FolderEntity(
            name,
            folder_type,
            parent_id=parent_id,
            entity_hub=self.entity_hub,
            attribs={self.ay_attrib: self._ay_value(own)},
        )
        self.ay_entities[name] = (folder, own, resolved)
        return self.entity_hub._add(folder, parent_id)

    def _add_task(self, name, folder_id, own, resolved):
        task = TaskEntity(
            name,
            "edit",
            folder_id=folder_id,
            entity_hub=self.entity_hub,
            attribs={self.ay_attrib: self._ay_value(own)},
        )
        self.ay_entities[name] = (task, own, resolved)
        return self.entity_hub._add(task, folder_id)

    def has_sg_field(self, sg_type):
        return self.sg_field in self.mg.schema_field_read(sg_type)

    def create_sg_entities(self, initial_states):
        """Create SG entities linked to AYON ones, with initial values."""
        parents = {"sh010": "seq", "sh020": "seq",
                   "task010": "sh010", "task020": "sh020"}
        step = self.mg.find_one("Step", [["code", "is", "edit"]])
        for name in ("seq", "sh010", "sh020", "task010", "task020"):
            ay_entity = self.ay_entities[name][0]
            sg_type = (
                "Task" if ay_entity.entity_type == "task"
                else ay_entity.folder_type
            )
            data = {
                "project": self.sg_project,
                constants.CUST_FIELD_CODE_ID: ay_entity.id,
            }
            if sg_type == "Task":
                data.update({
                    "content": name,
                    "entity": self.sg_entities[parents[name]],
                    "step": step,
                })
            else:
                data["code"] = name
                if sg_type == "Shot":
                    data["sg_sequence"] = self.sg_entities[parents[name]]
            if self.has_sg_field(sg_type):
                data[self.sg_field] = self.values[initial_states[name]][1]

            sg_entity = self.mg.create(sg_type, data)
            self.sg_entities[name] = sg_entity
            ay_entity.attribs.set(
                constants.SHOTGRID_ID_ATTRIB, str(sg_entity["id"]))
            ay_entity.attribs.set(constants.SHOTGRID_TYPE_ATTRIB, sg_type)

    def server_entity(self, name):
        """AYON server data, `ownAttrib` has None for inherited values."""
        ay_entity, own, resolved = self.ay_entities[name]
        attrib = {
            self.ay_attrib: self._ay_value(resolved),
            constants.SHOTGRID_ID_ATTRIB: ay_entity.attribs.get(
                constants.SHOTGRID_ID_ATTRIB),
            constants.SHOTGRID_TYPE_ATTRIB: ay_entity.attribs.get(
                constants.SHOTGRID_TYPE_ATTRIB),
        }
        data = {
            "id": ay_entity.id,
            "attrib": attrib,
            "ownAttrib": {self.ay_attrib: self._ay_value(own)},
        }
        if ay_entity.entity_type == "task":
            data["folderId"] = ay_entity.parent_id
        else:
            data["parentId"] = ay_entity.parent_id
        return data

    def server_entities(self, entity_type):
        return [
            self.server_entity(name)
            for name, (ay_entity, _, _) in self.ay_entities.items()
            if ay_entity.entity_type == entity_type
        ]

    def assert_sg_values(self):
        """SG must hold the values resolved by AYON."""
        for name, (ay_entity, _, resolved) in self.ay_entities.items():
            sg_type = (
                "Task" if ay_entity.entity_type == "task"
                else ay_entity.folder_type
            )
            if not self.has_sg_field(sg_type):
                continue
            filters = [[constants.CUST_FIELD_CODE_ID, "is", ay_entity.id]]
            sg_entity = self.mg.find_one(sg_type, filters, [self.sg_field])
            assert sg_entity, f"{name} not found in SG"
            assert sg_entity[self.sg_field] == self.values[resolved][1], name


def _run_full_sync(scenario):
    def get_folder_by_id(_project_name, folder_id, **_kwargs):
        return scenario.server_entity(_name_by_id(scenario, folder_id))

    def get_task_by_id(_project_name, task_id, **_kwargs):
        return scenario.server_entity(_name_by_id(scenario, task_id))

    with mock.patch.object(ayon_api, "get_folders", return_value=scenario.server_entities("folder")), \
         mock.patch.object(ayon_api, "get_tasks", return_value=scenario.server_entities("task")), \
         mock.patch.object(ayon_api, "get_folder_by_id", side_effect=get_folder_by_id), \
         mock.patch.object(ayon_api, "get_task_by_id", side_effect=get_task_by_id), \
         mock.patch.object(ayon_api, "get_versions", return_value=[]), \
         mock.patch.object(ayon_api, "get_entity_lists", return_value=[], create=True), \
         mock.patch.object(utils, "get_sg_project_enabled_entities", return_value=helpers.ENABLED_ENTITIES.items()):
        match_ayon_hierarchy_in_shotgrid(
            scenario.entity_hub,
            scenario.sg_project,
            scenario.mg,
            SG_ENABLED_ENTITIES,
            "code",
            scenario.custom_attribs_map,
            ADDON_SETTINGS,
        )


def _name_by_id(scenario, entity_id):
    for name, (ay_entity, _, _) in scenario.ay_entities.items():
        if ay_entity.id == entity_id:
            return name


@pytest.mark.parametrize("ay_attrib, sg_attrib, values", ATTRIB_CASES)
def test_manual_sync_update(mockgun_project, ay_attrib, sg_attrib, values):
    """Existing SG entities get the inherited values."""
    mg, sg_project = mockgun_project
    scenario = Scenario(mg, sg_project, ay_attrib, sg_attrib, values)
    scenario.create_sg_entities({
        "seq": "old", "sh010": "old", "task010": "old",
        "sh020": "own", "task020": "own",
    })

    _run_full_sync(scenario)

    scenario.assert_sg_values()


@pytest.mark.parametrize("ay_attrib, sg_attrib, values", ATTRIB_CASES)
def test_manual_sync_create(mockgun_project, ay_attrib, sg_attrib, values):
    """New SG entities are created with the inherited values."""
    mg, sg_project = mockgun_project
    scenario = Scenario(mg, sg_project, ay_attrib, sg_attrib, values)

    _run_full_sync(scenario)

    scenario.assert_sg_values()


@pytest.mark.parametrize("ay_attrib, sg_attrib, values", ATTRIB_CASES)
def test_event_sync(hub_and_project, ay_attrib, sg_attrib, values):
    """Changing an attribute on a folder updates the inheriting children."""
    mg = hub_and_project["mg"]
    hub = hub_and_project["hub"]
    scenario = Scenario(
        mg, hub_and_project["project"], ay_attrib, sg_attrib, values)
    scenario.create_sg_entities({
        "seq": "old", "sh010": "old", "task010": "old",
        "sh020": "own", "task020": "own",
    })
    seq_entity = scenario.ay_entities["seq"][0]

    ay_event = {
        "topic": "entity.folder.attrib_changed",
        "project": "test_project",
        "payload": {
            "oldValue": {ay_attrib: values["old"][0]},
            "newValue": {ay_attrib: values["new"][0]},
        },
        "summary": {"entityId": seq_entity.id, "parentId": "test_project"},
        "user": "admin",
    }

    def get_folders(_project_name, parent_ids=None, **_kwargs):
        return [
            folder for folder in scenario.server_entities("folder")
            if folder["parentId"] in parent_ids
        ]

    def get_tasks(_project_name, folder_ids=None, **_kwargs):
        return [
            task for task in scenario.server_entities("task")
            if task["folderId"] in folder_ids
        ]

    hub.custom_attribs_map = scenario.custom_attribs_map

    with mock.patch.object(EntityHub, "get_or_query_entity_by_id", return_value=seq_entity), \
         mock.patch.object(ayon_api, "get_folders", side_effect=get_folders), \
         mock.patch.object(ayon_api, "get_tasks", side_effect=get_tasks), \
         mock.patch.object(mg, "batch", wraps=mg.batch) as batch_mock:
        hub.react_to_ayon_event(ay_event)

    scenario.assert_sg_values()

    # Only the children whose value changed are written.
    expected = {"task010"}
    if scenario.has_sg_field("Shot"):
        expected.add("sh010")
    batch_mock.assert_called_once()
    updated = {
        (request["entity_type"], request["entity_id"])
        for request in batch_mock.call_args.args[0]
    }
    assert updated == {
        (scenario.sg_entities[name]["type"], scenario.sg_entities[name]["id"])
        for name in expected
    }
