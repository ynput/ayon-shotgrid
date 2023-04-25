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

    def _get_sg_entities_by_id(self, context, sg_session):
        """ Get all instances assets from Shotgrid.

        We loop over all the instances and gather all the assets so we can
        perform one Shotgrid query and get all Assets, then build a dict by
        their IDs.

        Args:
            context (pyblish.Plugin.context): The current publish context.
            sg_session (shotgun_api3.Shotgun): Connected Shotgrid api session.

        Returns:
            tuple[dict[int, Any], dict[int, Any]]: All the found Assets,
                with their ID as key and the Shotgrid entity dict as value
                and found tasks.
        """

        folder_ids = set()
        sg_assets_by_type = collections.defaultdict(set)
        task_names_by_sg_id = collections.defaultdict(set)
        for instance in context:
            ayon_folder = instance.data.get("assetEntity")
            if not ayon_folder:
                continue

            task_name = instance.data.get("task")
            folder_ids.add(ayon_folder["_id"])
            sg_id = ayon_folder["data"].get("shotgridId")
            sg_type = ayon_folder["data"].get("shotgridType")
            if sg_id and sg_type:
                sg_id = int(sg_id)
                sg_assets_by_type[sg_type].add(sg_id)
                task_names_by_sg_id[sg_id].add(task_name)

        sg_assets_by_id = {}
        for sg_type, sg_ids in sg_assets_by_type.items():
            sg_assets = self._query_sg_by_ids(
                sg_session,
                sg_type,
                sg_ids
            )
            for sg_asset in sg_assets:
                sg_assets_by_id[sg_asset["id"]] = sg_asset

        sg_tasks_by_asset_id = self._get_sg_tasks_by_id(
            sg_session, sg_assets_by_id, task_names_by_sg_id
        )
        return sg_assets_by_id, sg_tasks_by_asset_id

    def _get_sg_tasks_by_id(
        self, sg_session, sg_assets_by_id, task_names_by_sg_id
    ):
        """Find tasks in Shotgrid.

        Tasks are found by names and their parent shotgrid ids.

        Args:
             sg_session (shotgun_api3.Shotgun): THe Shotgrid session.
             sg_assets_by_id (dict[int, dict[str, Any]]): Queried Shotgrid
                entities by id.
            task_names_by_sg_id (dict[int, set[str]]): Task names by Shotgrid
                entity id.

        Returns:
            dict[int, dict[str, dict[str, Any]]]: All the found tasks by name
                and by shotgrid entity id.
        """

        sg_tasks_by_asset_id = {
            asset_id: {}
            for asset_id in task_names_by_sg_id
        }

        filters = []
        for sg_id, task_names in task_names_by_sg_id.items():
            sg_entity = sg_assets_by_id.get(sg_id)
            if not sg_entity:
                continue

            # Parent id filter need a type in field ('entity.Asset.id')
            parent_filter_field = "entity.{}.id".format(sg_entity["type"])
            filters.append({
                "filter_operator": "all",
                "filters": [
                    [parent_filter_field, "is", sg_id],
                    ["content", "in", list(task_names)]
                ]
            })

        if not filters:
            return sg_tasks_by_asset_id

        sg_tasks = sg_session.find(
            "Task",
            filters=filters,
            fields=["content", "entity"],
            filter_operator="any"
        )
        for sg_task in sg_tasks:
            parent_id = sg_task["entity"]["id"]
            task_name = sg_task["content"]
            sg_tasks_by_asset_id[parent_id][task_name] = sg_task

        return sg_tasks_by_asset_id

    def _query_sg_by_ids(
        self, sg_session, sg_type, sg_asset_ids, query_fields=None
    ):
        """ Query a list of IDs of a type from Shotgrid.

        Args:
            sg_session (shotgun_api3.Shotgun): THe Shotgrid session.
            sg_type (str): The asset type to query.
            sg_asset_ids (set[int]): The list of IDs to query.
            query_fields (Optional[list[str]]): Fields to get.
        """

        if not sg_asset_ids:
            return []

        if not query_fields:
            query_fields = []

        query_dict = {
            "filter_operator": "any",
            "filters": [
                ["id", "in", list(sg_asset_ids)]
            ]
        }

        return sg_session.find(
            sg_type,
            filters=[query_dict],
            fields=query_fields,
        )
