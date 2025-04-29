""" Test rename entity sync.
"""
import mock

from shotgun_api3.lib import mockgun

import ayon_api
from ayon_api.entity_hub import EntityHub, FolderEntity, TaskEntity, VersionEntity

from ayon_shotgrid_hub import AyonShotgridHub
import constants
import utils

from ..test_sg_base import TestBaseShotgrid


class TestUpdateEntityToSG(TestBaseShotgrid):
    """ Test update shotgrid entity.
    """

    def test_update_folder(self):
        """ Set width on a folder get reported in SG.
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

    def test_update_folder_status(self):
        """  Change status on a folder get reported in SG.
        """
        sg_shot = self.mg.create(
            "Shot",
            {
                "project": self.project,
                "code": "my_shot",
                "sg_status_list": "ip",
            }
        )

        ay_event = {
            'createdAt': '2025-04-29T17:46:37.839555+00:00',
            'dependsOn': None,
            'description': 'Changed shot my_shot status to Final',
            'hash': 'e66ac7e0252111f0ac900242ac120002',
            'id': 'e66ac7e0252111f0ac900242ac120002',
            'payload': {
                'newValue': 'Final',
                'oldValue': 'Waiting to Start'
            },
            'project': 'test_project',
            'retries': 0,
            'sender': '1YWHoUnmujGNUKwXWuiLvP',
            'senderType': 'api',
            'status': 'finished',
            'summary': {
                'entityId': '18fdb2eb1fac11f09d367cb566e6652d',
                'parentId': '11d9f4cd1fac11f099587cb566e6652d'
            },
            'topic': 'entity.folder.status_changed',
            'updatedAt': '2025-04-29T17:46:37.839555+00:00',
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
            ["sg_status_list"]
        )[0]

        self.assertEquals(
            {'id': 1, 'sg_status_list': 'fin', 'type': 'Shot'},
            shot
        )

    def test_update_task_status(self):
        """  Change status on a task get reported in SG.
        """
        sg_shot = self.mg.create(
            "Shot",
            {
                "project": self.project,
                "code": "my_shot",
                "sg_status_list": "ip",
            }
        )
        pipeline_step = self.mg.create(
            "Step",
            {
                "code": "edit",
                "entity_type": "Shot",
            }
        )
        sg_task = self.mg.create(
            "Task",
            {
                "project": self.project,
                "entity": sg_shot,
                "sg_status_list": "ip",
                "step": pipeline_step,
            }
        )

        ay_event = {
            'createdAt': '2025-04-29T17:46:37.839555+00:00',
            'dependsOn': None,
            'description': 'Changed task my_task status to Final',
            'hash': 'e66ac7e0252111f0ac900242ac120002',
            'id': 'e66ac7e0252111f0ac900242ac120002',
            'payload': {
                'newValue': 'Final',
                'oldValue': 'In Progress'
            },
            'project': 'test_project',
            'retries': 0,
            'sender': '1YWHoUnmujGNUKwXWuiLvP',
            'senderType': 'api',
            'status': 'finished',
            'summary': {
                'entityId': '18fdb2eb1fac11f09d367cb566e6652d',
                'parentId': '11d9f4cd1fac11f099587cb566e6652d'
            },
            'topic': 'entity.task.status_changed',
            'updatedAt': '2025-04-29T17:46:37.839555+00:00',
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

        task_entity = TaskEntity(
            "new_task",
            task_type="edit",
            folder_id="11d9f4cd1fac11f099587cb566e6652d",  # parent to sequence
            entity_id="18fdb2eb1fac11f09d367cb566e6652d",  # task entity id
            entity_hub=self.entity_hub,
            attribs={
                constants.SHOTGRID_ID_ATTRIB: str(sg_task["id"]),
                constants.SHOTGRID_TYPE_ATTRIB: "Task",
            }
        )

        # Associate folder entity to event.
        with mock.patch.object(
            EntityHub,
            "get_or_query_entity_by_id",
            return_value=task_entity,
        ):
            self.hub.react_to_ayon_event(ay_event)

        task = self.mg.find(
            "Task",
            [["project", "is", self.project]],
            ["sg_status_list", "step"]
        )[0]

        self.assertEquals(
            {
                'id': 1,
                'sg_status_list': 'fin',
                'type': 'Task',
                'step': {'id': 1, 'type': 'Step'}
            },
            task,
        )

    def test_task_assignee_update(self):
        """  Check valid assignee on a task get reported in SG.
        """
        pipeline_step = self.mg.create(
            "Step",
            {
                "code": "edit",
                "entity_type": "Shot",
            }
        )
        sg_task = self.mg.create(
            "Task",
            {
                "project": self.project,
                "sg_status_list": "ip",
                "step": pipeline_step,
            }
        )
        sg_user = self.mg.create(
            "HumanUser",
            {
                "login": "test_user@email.com",
                "name": "test_user",
            }
        )

        ay_event = {
            'createdAt': '2025-04-29T18:01:27.346534+00:00',
            'dependsOn': None,
            'description': 'Changed task edit_task assignees',
            'hash': 'f89abfb8252311f0ac900242ac120002',
            'id': 'f89abfb8252311f0ac900242ac120002',
            'payload': {
                'newValue': ['test_user'],
                'oldValue': []
            },
            'project': 'robin_test_project',
            'retries': 0,
            'sender': '8SLvrKnT7mYmSVFLz8PmRp',
            'senderType': 'api',
            'status': 'finished',
            'summary': {
                'entityId': 'a40c7e401fb111f0873b9b5f33da4c09',
                'parentId': '18fdb2eb1fac11f09d367cb566e6652d'
            },
            'topic': 'entity.task.assignees_changed',
            'updatedAt': '2025-04-29T18:01:27.346534+00:00',
            'user': 'admin'
        }

        task_entity = TaskEntity(
            "new_task",
            task_type="edit",
            folder_id="11d9f4cd1fac11f099587cb566e6652d",  # parent to sequence
            entity_id="18fdb2eb1fac11f09d367cb566e6652d",  # task entity id
            entity_hub=self.entity_hub,
            attribs={
                constants.SHOTGRID_ID_ATTRIB: str(sg_task["id"]),
                constants.SHOTGRID_TYPE_ATTRIB: "Task",
            }
        )

        # Associate folder entity to event.
        with mock.patch.object(
            EntityHub,
            "get_or_query_entity_by_id",
            return_value=task_entity,
        ):
            with mock.patch.object(
                ayon_api,
                "get_user",
                return_value={'name': 'test_user', "data": {"sg_user_id": 1}}
            ):
                self.hub.react_to_ayon_event(ay_event)

        task = self.mg.find(
            "Task",
            [["project", "is", self.project]],
            ["task_assignees"]
        )[0]

        self.assertEquals(
            {
                'id': 1,
                'task_assignees': [{'id': 1, 'type': 'HumanUser'}],
                'type': 'Task',
            },
            task,
        )

    def test_task_invalid_assignee_update(self):
        """  Check invalid assignee on a task get reported in SG.
        """
        pipeline_step = self.mg.create(
            "Step",
            {
                "code": "edit",
                "entity_type": "Shot",
            }
        )
        sg_task = self.mg.create(
            "Task",
            {
                "project": self.project,
                "sg_status_list": "ip",
                "step": pipeline_step,
            }
        )

        ay_event = {
            'createdAt': '2025-04-29T18:01:27.346534+00:00',
            'dependsOn': None,
            'description': 'Changed task edit_task assignees',
            'hash': 'f89abfb8252311f0ac900242ac120002',
            'id': 'f89abfb8252311f0ac900242ac120002',
            'payload': {
                'newValue': ['missing_user'],
                'oldValue': []
            },
            'project': 'robin_test_project',
            'retries': 0,
            'sender': '8SLvrKnT7mYmSVFLz8PmRp',
            'senderType': 'api',
            'status': 'finished',
            'summary': {
                'entityId': 'a40c7e401fb111f0873b9b5f33da4c09',
                'parentId': '18fdb2eb1fac11f09d367cb566e6652d'
            },
            'topic': 'entity.task.assignees_changed',
            'updatedAt': '2025-04-29T18:01:27.346534+00:00',
            'user': 'admin'
        }

        task_entity = TaskEntity(
            "new_task",
            task_type="edit",
            folder_id="11d9f4cd1fac11f099587cb566e6652d",  # parent to sequence
            entity_id="18fdb2eb1fac11f09d367cb566e6652d",  # task entity id
            entity_hub=self.entity_hub,
            attribs={
                constants.SHOTGRID_ID_ATTRIB: str(sg_task["id"]),
                constants.SHOTGRID_TYPE_ATTRIB: "Task",
            }
        )

        # Associate folder entity to event.
        with mock.patch.object(
            EntityHub,
            "get_or_query_entity_by_id",
            return_value=task_entity,
        ):
            with mock.patch.object(
                ayon_api,
                "get_user",
                return_value={'name': 'missing_user'}  # user not synced with SG
            ):
                self.hub.react_to_ayon_event(ay_event)

        task = self.mg.find(
            "Task",
            [["project", "is", self.project]],
            ["task_assignees"]
        )[0]

        self.assertEquals(
            {
                'id': 1,
                'task_assignees': [],
                'type': 'Task',
            },
            task,
        )
