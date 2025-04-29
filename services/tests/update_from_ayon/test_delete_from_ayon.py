""" Test delete entity sync.
"""
import mock

from shotgun_api3.lib import mockgun

from ayon_api.entity_hub import EntityHub, FolderEntity, TaskEntity, VersionEntity

from ayon_shotgrid_hub import AyonShotgridHub
import constants
import utils

from ..test_sg_base import TestBaseShotgrid


class TestDeleteEntityToSG(TestBaseShotgrid):
    """ Test delete shotgrid entity.
    """

    def test_delete_folder(self):
        """ Delete folder reported in SG.
        """
        sg_sequence = self.mg.create(
            "Sequence",
            {
                "project": self.project,
                "code": "my_sequence",
            }
        )

        ay_event = {
            'createdAt': '2025-04-29T17:02:17.951175+00:00',
            'dependsOn': None,
            'description': 'Folder my_new_episode deleted',
            'hash': 'b4ffe7d6251b11f0ac900242ac120002',
            'id': 'b4ffe7d6251b11f0ac900242ac120002',
            'payload': {
                'entityData': {
                    'active': True,
                    'attrib': {
                        'shotgridId': '1',
                        'shotgridType': 'Sequence'
                    },
                    'createdAt': '2025-04-29T14:10:34.591721+00:00',
                    'data': {},
                    'folderType': 'Sequence',
                    'id': 'b6add2e0250311f08eedd9567d7d6404',
                    'name': 'my_new_sequence',
                    'path': '/my_new_sequence',
                    'status': 'Not ready',
                    'tags': [],
                    'updatedAt': '2025-04-29T15:38:21.775660+00:00'
                }
            },
            'project': 'test_project',
            'retries': 0,
            'sender': '1YWHoUnmujGNUKwXWuiLvP',
            'senderType': 'api',
            'status': 'finished',
            'summary': {'entityId': 'b6add2e0250311f08eedd9567d7d6404', 'parentId': None},
            'topic': 'entity.folder.deleted',
            'updatedAt': '2025-04-29T17:02:17.951175+00:00',
            'user': 'admin'
        }

        sequence_entity = FolderEntity(
            "new_sequence",
            "Sequence",
            parent_id=None,  # no parent
            entity_hub=self.entity_hub,
            attribs={
                constants.SHOTGRID_ID_ATTRIB: str(sg_sequence["id"]),
                constants.SHOTGRID_TYPE_ATTRIB: "Sequence",
            }
        )

        self.hub.react_to_ayon_event(ay_event)

        no_sequences = self.mg.find(
            "Sequence",
            [["project", "is", self.project]],
        )

        self.assertEquals([], no_sequences)
