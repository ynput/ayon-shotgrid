""" Base class to test Shotgrid implementation via Mockgun.
"""
import constants


def test_hub_initialization(hub_and_project):
    """ Example test to validate the hub object was created correctly. """
    hub = hub_and_project["hub"]
    assert hub.sg_enabled_entities == ("Episode", "Sequence", "Shot", "Asset")


def test_project_entity_attributes(hub_and_project):
    """ Validate attributes of the mocked FolderEntity. """
    entity = hub_and_project["project_entity"]
    assert entity.attribs[constants.SHOTGRID_TYPE_ATTRIB] == "Project"
