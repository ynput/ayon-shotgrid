""" Test rename entity sync.
"""
import mock

from shotgun_api3.lib import mockgun

from ayon_api.entity_hub import EntityHub, FolderEntity, TaskEntity, VersionEntity

from ayon_shotgrid_hub import AyonShotgridHub
import constants
import utils

from ..test_sg_base import TestBaseShotgrid


class TestUpdateEntityToSG(TestBaseShotgrid):
    """ Test update shotgrid entity.
    """

    def test_rename_folder(self):
        """ Delete renamed folder in SG.
        """
        sg_shot = self.mg.create(
            "Shot",
            {
                "project": self.project,
                "code": "my_shot",
            }
        )

        ay_event = {
            'createdAt': '2025-04-29T17:20:22.422755+00:00',
            'dependsOn': None,
            'description': 'Changed folder my_shot attributes: resolutionWidth',
            'hash': '3b654634251e11f0ac900242ac120002',
            'id': '3b654634251e11f0ac900242ac120002',
            'payload': {
                'newValue': {'resolutionWidth': 250},
                'oldValue': {'resolutionWidth': 1920}},
            'project': 'test_project',
            'retries': 0,
            'sender': '1YWHoUnmujGNUKwXWuiLvP',
            'senderType': 'api',
            'status': 'finished',
            'summary': {
                'entityId': '18fdb2eb1fac11f09d367cb566e6652d',
                'parentId': '11d9f4cd1fac11f099587cb566e6652d'
            },
            'topic': 'entity.folder.attrib_changed',
            'updatedAt': '2025-04-29T17:20:22.422755+00:00',
            'user': 'admin'
        }

        shot_entity = FolderEntity(
            "new_shot",
            "Shot",
            parent_id=None,  # no parent
            entity_hub=self.entity_hub,
            attribs={
                constants.SHOTGRID_ID_ATTRIB: str(sg_shot["id"]),
                constants.SHOTGRID_TYPE_ATTRIB: "Shot",
            }
        )

        self.hub.custom_attribs_map = {"resolutionWidth": "sg_resolution_width"}

        # Associate folder entity to event.
        with mock.patch.object(
            EntityHub,
            "get_or_query_entity_by_id",
            return_value=shot_entity,
        ):
            self.hub.react_to_ayon_event(ay_event)

        shot = self.mg.find(
            "Shot",
            [["project", "is", self.project]],
            ["sg_resolution_width"]
        )[0]

        self.assertEquals(
            {'id': 1, 'sg_resolution_width': 250, 'type': 'Shot'},
            shot
        )
