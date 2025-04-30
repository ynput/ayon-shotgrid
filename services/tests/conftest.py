import pytest

from shotgun_api3.lib import mockgun

from ayon_api.entity_hub import EntityHub, FolderEntity

from ayon_shotgrid_hub import AyonShotgridHub
import constants


class MockEntityHub(EntityHub):
    def __init__(self, project_name, connection=None):
        self._connection = connection
        self._project_name = project_name

    def get_attributes_for_type(self, _):
        return {
            constants.SHOTGRID_ID_ATTRIB: str,
            constants.SHOTGRID_TYPE_ATTRIB: str
        }

    def commit_changes(self):
        return


class MockFolderEntity(FolderEntity):
    pass


@pytest.fixture
def mockgun_project():
    """Fixture that returns a mockgun instance and a created project."""
    mg = mockgun.Shotgun("http://random_url")
    project = mg.create(
        "Project",
        {
            "code": "test",
            "name": "test_project",
            "sg_ayon_auto_sync": True,
        }
    )
    return mg, project


@pytest.fixture
def hub_and_project(mockgun_project):
    """Fixture that sets up the AyonShotgridHub and related mock entities."""
    mg, project = mockgun_project

    hub = AyonShotgridHub(
        mg,
        "test_project",
        "test",
        sg_project_code_field="code",
        sg_enabled_entities=(
            "Episode",
            "Sequence",
            "Shot",
            "Asset",
        ),
    )

    entity_hub = MockEntityHub("test_project")

    project_entity = MockFolderEntity(
        "test_project",
        "Project",
        parent_id=None,
        entity_hub=entity_hub,
        attribs={
            constants.SHOTGRID_ID_ATTRIB: str(project["id"]),
            constants.SHOTGRID_TYPE_ATTRIB: "Project",
        }
    )

    # Inject mock entity hub into the hub
    hub._ay_project = entity_hub

    return {
        "hub": hub,
        "entity_hub": entity_hub,
        "project_entity": project_entity,
        "mg": mg,
        "project": project,
    }
