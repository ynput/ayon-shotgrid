""" Base class to test Shotgrid implementation via Mockgun.
"""
import mock
import unittest

from shotgun_api3.lib import mockgun

from ayon_api.entity_hub import EntityHub, FolderEntity

from ayon_shotgrid_hub import AyonShotgridHub
import constants


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

        self.entity_hub = EntityHub("test_project")
        self.entity_hub.commit_changes = mock.Mock(return_value=None)  # do nothing

        self.project_entity = FolderEntity(
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
