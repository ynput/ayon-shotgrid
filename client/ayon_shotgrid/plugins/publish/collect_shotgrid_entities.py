import collections

import pyblish.api

from openpype.pipeline import KnownPublishError


class CollectShotgridEntities(pyblish.api.ContextPlugin):
    """Collect shotgrid entities according to the current context."""

    order = pyblish.api.CollectorOrder + 0.499
    label = "Collect Shotgrid Assets and Tasks."

    def process(self, context):
        if not context.data.get("shotgridSession"):
            raise KnownPublishError(
                "Unable to proceeed without a valid Shotgrid Session."
            )

        sg_session = context.data["shotgridSession"]
        ayon_project = context.data["projectEntity"]
        sg_project_id = ayon_project["data"].get("shotgridId")

        if not sg_project_id:
            raise KnownPublishError(
                "AYON is missing the Shotgrid project ID.")

        sg_project = sg_session.find_one(
            "Project",
            filters=[["id", "is", int(sg_project_id)]]
        )
        if not sg_project:
            raise KnownPublishError((
                "Project '{}' was not found in Shotgrid by id '{}'."
            ).format(ayon_project["name"], sg_project_id))

        context.data["shotgridProject"] = sg_project

        self.log.info(
            "Collected corresponding shotgrid project: {}".format(sg_project)
        )

        sg_entities_by_id, sg_tasks_by_id = self._get_sg_entities_by_id(
            context, sg_session)

        for instance in context:
            ayon_asset = instance.data.get("assetEntity")
            # Skip instance with missing asset - probably in editorial
            if not ayon_asset:
                continue

            sg_asset_id = ayon_asset["data"].get("shotgridId")
            if sg_asset_id is not None:
                sg_asset_id = int(sg_asset_id)

            sg_asset = sg_entities_by_id.get(sg_asset_id)
            self.log.debug(
                "Collected Instance Shotgrid Asset: {}".format(sg_asset)
            )

            task_name = instance.data.get("task")
            sg_task = None
            if sg_asset:
                sg_task = sg_tasks_by_id.get(sg_asset_id, {}).get(task_name)

            self.log.debug(
                "Collected Instance Shotgrid Task: {}".format(sg_task)
            )
            instance.data["shotgridProject"] = sg_project
            instance.data["shotgridEntity"] = sg_asset
            instance.data["shotgridTask"] = sg_task

    def _get_sg_tasks_by_id(self, context):
        """ Get all instances tasks from Shotgrid.

        We loop over all the instances and gather all the tasks so we can
        perform one Shotgird query and get all Tasks, then build a dict by their
        IDs.

        Args:
            context (pyblish.Plugin.context): The current publish context.

        Returns:
            sg_tasks_by_id (dict): All the found tasks, with their ID as key
                and the Shotgrid entity dict as value.
        """
        sg_session = context.data["shotgridSession"]
        sg_tasks_ids = []
        sg_tasks_by_id = {}

        ayon_folder_ids = [
            instance.data.get("assetEntity").get("_id")
            for instance in context
            if instance.data.get("assetEntity").get("_id")
        ]

        ayon_tasks = list(ayon_api.get_tasks(
            context.data["projectName"],
            folder_ids=ayon_folder_ids
        ))

        for instance in context:
            ayon_asset = instance.data.get("assetEntity")
            ayon_task_name = instance.data.get("task")
            ayon_task = None

            if not ayon_task_name:
                continue

            for task in ayon_tasks:
                if (
                    task['folderId'] == ayon_asset["_id"]
                    and ayon_task_name == task["name"]
                ):
                    ayon_task = task

            if not ayon_task:
                continue

            sg_task_id = ayon_task.get("attrib", {}).get("shotgridId")

            if not sg_task_id:
                continue

            sg_tasks_ids.append(int(sg_task_id))

        for sg_task in self._query_sg_by_ids(
            sg_session,
            "Task",
            sg_tasks_ids,
            query_fields=["content"]
         ):
            sg_tasks_by_id[sg_task["id"]] = sg_task

        return sg_tasks_by_id

    def _get_sg_assets_by_id(self, context):
        """ Get all instances assets from Shotgrid.

        We loop over all the instances and gather all the assets so we can
        perform one Shotgird query and get all Assets, then build a dict by
        their IDs.

        Args:
            context (pyblish.Plugin.context): The current publish context.

        Returns:
            sg_tasks_by_id (dict): All the found Assets, with their ID as key
                and the Shotgrid entity dict as value.
        """
        sg_session = context.data["shotgridSession"]
        sg_assets_by_type = {}
        sg_assets_by_id = {}

        for instance in context:
            ayon_asset = instance.data.get("assetEntity")
            sg_asset_id = ayon_asset.get("data", {}).get("shotgridId")
            sg_asset_type = ayon_asset.get("data", {}).get("shotgridType")

            if sg_asset_id and sg_asset_type:
                sg_assets_by_type.setdefault(sg_asset_type, []) 
                sg_assets_by_type[sg_asset_type].append(sg_asset_id)

        for sg_asset_type, sg_asset_ids in sg_assets_by_type.items():
            sg_assets = self._query_sg_by_ids(
                sg_session,
                sg_asset_type,
                sg_asset_ids
            )

            for sg_asset in sg_assets:
                sg_assets_by_id[sg_asset["id"]] = sg_asset

        return sg_assets_by_id

    def _query_sg_by_ids(self, sg_session, sg_type, ids_list, query_fields=None):
        """ Query a list of IDs of a type from Shotgrid.
        
        Args:
            sg_sesion (shotgun_api3.Shotgun): THe Shotgrid session.
            sg_type (str): The asset type to query.
            ids_list (list): The list of IDs to query.
        """
        if not query_fields:
            query_fields = []

        query_dict = {
                "filter_operator": "any",
                "filters": []
            }

        for sg_id in ids_list:
            query_dict["filters"].append(["id", "is", int(sg_id)])

        return sg_session.find(
            sg_type,
            filters=[query_dict],
            fields=query_fields,
        )

