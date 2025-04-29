""" Test delete entity sync.
"""




from ..test_sg_base import TestBaseShotgrid


class TestDeleteEntityToSG(TestBaseShotgrid):
    """ Test delete shotgrid entity.
    """

    def test_delete_folder(self):
        """ Delete folder reported in SG.
        """
        self.mg.create(  # create one sequence
            "Sequence",
            {
                "project": self.project,
                "code": "my_sequence",
            }
        )

        all_sequences = self.mg.find(
            "Sequence",
            [["project", "is", self.project]],
        )

        self.assertEquals(1, len(all_sequences))


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

        self.hub.react_to_ayon_event(ay_event)

        no_sequences = self.mg.find(
            "Sequence",
            [["project", "is", self.project]],
        )

        self.assertEquals([], no_sequences)
