""" 
"""
import unittest

from shotgun_api3.lib import mockgun

from shotgrid_common import _shotgrid


class TestShotgrid(unittest.TestCase):
    """ Test shotgrid helpers
    """

    def setUp(self):
        """
        """
        self.mg = mockgun.Shotgun("http://random_url")

    def test_retrieve_entity(self):
        """ entity is retrieved
        """
        project = self.mg.create(
            "Project",
            {
                "code": "test",
                "name": "test_project",
            }
        )

        result = _shotgrid.get_entity("Project", project["id"], sg=self.mg)
        self.assertTrue(result.items() <= project.items())

    def test_retrieve_entity_missing(self):
        """ entity is missing
        """
        with self.assertRaises(ValueError):
            _ = _shotgrid.get_entity("Project", 12345, sg=self.mg)

    def test_retrieve_entity_allow_none(self):
        """ entity is missing but that's ok
        """
        result = _shotgrid.get_entity(
            "Project",
            12345,
            allow_none=True,
            sg=self.mg
        )

        self.assertIsNone(result)