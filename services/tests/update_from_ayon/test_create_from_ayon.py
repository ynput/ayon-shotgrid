""" Test entity sync.
"""
import mock

from shotgun_api3.lib import mockgun

from ayon_api.entity_hub import EntityHub, FolderEntity, TaskEntity, VersionEntity

from ayon_shotgrid_hub import AyonShotgridHub
import constants
import utils

from ..test_sg_base import TestBaseShotgrid


class TestSyncEntityToSG(TestBaseShotgrid):
    """ Test create shotgrid entity.
    """

    def test_create_new_episode(self):
        """ Check new episode folder is properly reported in SG.
        """
        ay_event = {
            'createdAt': '2025-04-29T14:10:34.642408+00:00',
            'dependsOn': None,
            'description': 'Folder my_new_episode created',
            'hash': 'b7bfe222250311f0ac900242ac120002',
            'id': 'b7bfe222250311f0ac900242ac120002',
            'payload': {},
            'project': 'test_project',
            'retries': 0,
            'sender': '1YWHoUnmujGNUKwXWuiLvP',
            'senderType': 'api',
            'status': 'finished',
            'summary': {'entityId': 'b6add2e0250311f08eedd9567d7d6404', 'parentId': None},
            'topic': 'entity.folder.created',
            'updatedAt': '2025-04-29T14:10:34.642408+00:00',
            'user': 'admin'
        }

        folder_entity = FolderEntity(
            "new_episode",
            "Episode",
            parent_id=None,  # no parent
            entity_hub=self.entity_hub,
        )

        # Associate folder entity to event.
        with mock.patch.object(
            EntityHub,
            "get_or_query_entity_by_id",
            return_value=folder_entity,
        ):
            # Reparent new episode to project.
            with mock.patch.object(
                FolderEntity,
                "parent",
                new_callable=mock.PropertyMock,
            ) as mock_parent:
                mock_parent.return_value = self.project_entity

                with mock.patch.object(
                    utils,
                    "get_sg_entity_parent_field",
                    return_value="project"
                ):
                    self.hub.react_to_ayon_event(ay_event)

        new_episode = self.mg.find(
            "Episode",
            [["project", "is", self.project]],
            ["code"]
        )[0]

        self.assertEquals(
            new_episode,
            {'code': 'new_episode', 'id': 1, 'type': 'Episode'},
        )


    def test_create_new_asset(self):
        """ Check new asset folder is properly reported in SG.
        """
        ay_event = {
            'createdAt': '2025-04-29T14:10:34.642408+00:00',
            'dependsOn': None,
            'description': 'Folder new_asset created',
            'hash': 'b7bfe222250311f0ac900242ac120002',
            'id': 'b7bfe222250311f0ac900242ac120002',
            'payload': {},
            'project': 'test_project',
            'retries': 0,
            'sender': '1YWHoUnmujGNUKwXWuiLvP',
            'senderType': 'api',
            'status': 'finished',
            'summary': {'entityId': 'b6add2e0250311f08eedd9567d7d6404', 'parentId': None},
            'topic': 'entity.folder.created',
            'updatedAt': '2025-04-29T14:10:34.642408+00:00',
            'user': 'admin'
        }

        folder_entity = FolderEntity(
            "new_asset",
            "Asset",
            parent_id=None,  # no parent
            entity_hub=self.entity_hub,
        )

        # Associate folder entity to event.
        with mock.patch.object(
            EntityHub,
            "get_or_query_entity_by_id",
            return_value=folder_entity,
        ):
            # Reparent new episode to project.
            with mock.patch.object(
                FolderEntity,
                "parent",
                new_callable=mock.PropertyMock,
            ) as mock_parent:
                mock_parent.return_value = self.project_entity

                with mock.patch.object(
                    utils,
                    "get_sg_entity_parent_field",
                    return_value="project"
                ):
                    self.hub.react_to_ayon_event(ay_event)

        new_episode = self.mg.find(
            "Asset",
            [["project", "is", self.project]],
            ["code"]
        )[0]

        self.assertEquals(
            new_episode,
            {'code': 'new_asset', 'id': 1, 'type': 'Asset'},
        )


    def test_create_new_shot(self):
        """ Check new shot is properly reported in SG.
        """
        sg_parent_sequence = self.mg.create(
            "Sequence",
            {
                "project": self.project,
                "code": "my_sequence",
            }
        )

        ay_event = {
            'createdAt': '2025-04-29T14:10:34.642408+00:00',
            'dependsOn': None,
            'description': 'Folder new_shot created',
            'hash': 'b7bfe222250311f0ac900242ac120002',
            'id': 'b7bfe222250311f0ac900242ac120002',
            'payload': {},
            'project': 'test_project',
            'retries': 0,
            'sender': '1YWHoUnmujGNUKwXWuiLvP',
            'senderType': 'api',
            'status': 'finished',
            'summary': {'entityId': 'b6add2e0250311f08eedd9567d7d6404', 'parentId': None},
            'topic': 'entity.folder.created',
            'updatedAt': '2025-04-29T14:10:34.642408+00:00',
            'user': 'admin'
        }

        sequence_entity = FolderEntity(
            "new_sequence",
            "Sequence",
            parent_id=None,  # no parent
            entity_hub=self.entity_hub,
            attribs={
                constants.SHOTGRID_ID_ATTRIB: str(sg_parent_sequence["id"]),
                constants.SHOTGRID_TYPE_ATTRIB: "Sequence",
            }
        )

        shot_entity = FolderEntity(
            "new_shot",
            "Shot",
            parent_id=sequence_entity.id,  # parented to sequence
            entity_hub=self.entity_hub,
        )

        # Associate folder entity to event.
        with mock.patch.object(
            EntityHub,
            "get_or_query_entity_by_id",
            return_value=shot_entity,
        ):
            # Reparent new episode to project.
            with mock.patch.object(
                FolderEntity,
                "parent",
                new_callable=mock.PropertyMock,
            ) as mock_parent:
                mock_parent.return_value = sequence_entity

                with mock.patch.object(
                    utils,
                    "get_sg_entity_parent_field",
                    return_value="sg_sequence"
                ):
                    self.hub.react_to_ayon_event(ay_event)

        new_shot = self.mg.find(
            "Shot",
            [["project", "is", self.project]],
            ["code", "sg_sequence"]
        )[0]

        self.assertEquals(
            new_shot,
            {
                'code': 'new_shot',
                'id': 1,
                'type': 'Shot',
                'sg_sequence': {'type': 'Sequence', 'id': 1},  # properly parented
            },
        )


    def test_create_new_task(self):
        """ Check new task is properly reported in SG.
        """
        sg_parent_sequence = self.mg.create(
            "Sequence",
            {
                "project": self.project,
                "code": "my_sequence",
            }
        )
        pipeline_step = self.mg.create(
            "Step",
            {
                "code": "edit",
                "entity_type": "Sequence",
            }
        )

        sequence_entity = FolderEntity(
            "new_sequence",
            "Sequence",
            parent_id=None,  # no parent
            entity_hub=self.entity_hub,
            attribs={
                constants.SHOTGRID_ID_ATTRIB: str(sg_parent_sequence["id"]),
                constants.SHOTGRID_TYPE_ATTRIB: "Sequence",
            }
        )

        ay_event = {
            'createdAt': '2025-04-29T15:45:23.550702+00:00',
            'dependsOn': None,
            'description': 'Task new_edit_task created',
            'hash': 'f69a64a6251011f0ac900242ac120002',
            'id': 'f69a64a6251011f0ac900242ac120002',
            'payload': {},
            'project': 'test_project',
            'retries': 0,
            'sender': '1YWHoUnmujGNUKwXWuiLvP',
            'senderType': 'api',
            'status': 'finished',
            'summary': {
                'entityId': 'f56a1540251011f08eedd9567d7d6404',
                'parentId': '11d9f4cd1fac11f099587cb566e6652d'
            },
            'topic': 'entity.task.created',
            'updatedAt': '2025-04-29T15:45:23.550702+00:00',
            'user': 'admin'
        }

        task_entity = TaskEntity(
            "new_task",
            task_type="edit",
            folder_id="11d9f4cd1fac11f099587cb566e6652d",  # parent to sequence
            entity_id="f56a1540251011f08eedd9567d7d6404",  # task entity id
            entity_hub=self.entity_hub,
        )

        # Associate folder entity to event.
        with mock.patch.object(
            EntityHub,
            "get_or_query_entity_by_id",
            return_value=task_entity,
        ):
            # Reparent new episode to project.
            with mock.patch.object(
                TaskEntity,
                "parent",
                new_callable=mock.PropertyMock,
            ) as mock_parent:
                mock_parent.return_value = sequence_entity

                with mock.patch.object(
                    utils,
                    "get_sg_entity_parent_field",
                    return_value="entity"
                ):
                    with mock.patch.object(utils, "_sg_to_ay_dict", return_value={}):
                        self.hub.react_to_ayon_event(ay_event)

        new_task = self.mg.find(
            "Task",
            [["project", "is", self.project]],
            ["code", "entity", "step"]
        )[0]

        self.assertEquals(
            new_task,
            {
                'code': None,
                'entity': {'id': 1, 'type': 'Sequence'},
                'step': {'id': 1, 'type': 'Step'},
                'id': 1, 'type': 'Task'
            }
        )
