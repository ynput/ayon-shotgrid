""" Base class to test Shotgrid implementation via Mockgun.
"""
import mock
import unittest

from shotgun_api3.lib import mockgun

from ayon_api.entity_hub import EntityHub, FolderEntity

from ayon_shotgrid_hub import AyonShotgridHub
import constants


class MockEntityHub(EntityHub):

    def __init__(self, project_name, connection=None):
        self._connection = connection
        self._project_name = project_name

    def get_attributes_for_type(self, entity_type: "EntityType"):
        return {
            constants.SHOTGRID_ID_ATTRIB: str,
            constants.SHOTGRID_TYPE_ATTRIB: str
        }

    def commit_changes(self):
        return


class MockFolderEntity(FolderEntity):
    pass


class TestBaseShotgrid(unittest.TestCase):
    """ Test shotgrid helper.
    """

    def setUp(self):
        """ Create a mockgun instance containing a project.
        """
        self.mg = mockgun.Shotgun("http://random_url")
        self.project = self.mg.create(
            "Project",
            {
                "code": "test",
                "name": "test_project",
                "sg_ayon_auto_sync": True,
            }
        )

        self.hub = AyonShotgridHub(
            self.mg,
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

        self.entity_hub = MockEntityHub("test_project")

        self.project_entity = MockFolderEntity(
            "test_project",
            "Project",
            parent_id=None,  # no parent
            entity_hub=self.entity_hub,
            attribs={
                constants.SHOTGRID_ID_ATTRIB: str(self.project["id"]),
                constants.SHOTGRID_TYPE_ATTRIB: "Project",
            }
        )

        self.hub._ay_project = self.entity_hub

