import pyblish.api

from openpype.pipeline.publish import get_publish_repre_path


class IntegrateShotgridVersion(pyblish.api.InstancePlugin):
    """Integrate Shotgrid Version"""
    order = pyblish.api.IntegratorOrder + 0.497
    label = "Shotgrid Version"

    def process(self, instance):
        sg_session = instance.context.data["shotgridSession"]

        # TODO: Use path template solver to build version code from settings
        anatomy = instance.data.get("anatomyData", {})
        version_name = "_".join(
            [
                anatomy["project"]["code"],
                anatomy["parent"],
                anatomy["asset"],
            ]
        )

        if instance.data["shotgridTask"]:
            version_name = "{0}_{1}".format(
                version_name,
                instance.data["shotgridTask"]["content"]
            )

        version_name = "{0}_{1}".format(
            version_name,
            "v{:03}".format(int(anatomy["version"]))
        )

        sg_version = self._find_existing_version(version_name, instance)

        if not sg_version:
            sg_version = self._create_version(version_name, instance)
            self.log.info("Create Shotgrid version: {}".format(sg_version))
        else:
            self.log.info("Use existing Shotgrid version: {}".format(sg_version))

        data_to_update = {}
        intent = instance.context.data.get("intent")
        if intent:
            data_to_update["sg_status_list"] = intent["value"]

        for representation in instance.data.get("representations", []):

            if "shotgridreview" not in representation.get("tags", []):
                continue

            local_path = get_publish_repre_path(
                instance, representation, False
            )

            if representation["ext"] in ["mov", "avi"]:
                self.log.info(
                    "Upload review: {} for version shotgrid {}".format(
                        local_path, sg_version.get("id")
                    )
                )
                self.sg_session.upload(
                    "Version",
                    sg_version.get("id"),
                    local_path,
                    field_name="sg_uploaded_movie",
                )

                data_to_update["sg_path_to_movie"] = local_path

            elif representation["ext"] in ["jpg", "png", "exr", "tga"]:
                path_to_frame = local_path.replace("0000", "#")
                data_to_update["sg_path_to_frames"] = path_to_frame

        self.log.info("Update Shotgrid version with {}".format(data_to_update))
        sg_session.update("Version", sg_version["id"], data_to_update)

        instance.data["shotgridVersion"] = sg_version

    def _find_existing_version(self, version_name, instance):
        """Find if a Version alread exists in Shotgrid.

        Args:
            version_name(str): The full version name, `code` field in SG.
            instance (pyblish.Instance): The version's Instance.

        Returns:
            dict/None: A Shogrid Version or None if there is none.
        """
        filters = [
            ["project", "is", instance.data.get("shotgridProject")],
            ["entity", "is", instance.data.get("shotgridEntity")],
            ["code", "is", version_name],
        ]

        if instance.data.get("shotgridTask"):
            filters.append(["sg_task", "is", instance.data.get("shotgridTask")])

        return instance.context.data["shotgridSession"].find_one(
            "Version",
            filters
        )

    def _create_version(self, version_name, instance):
        """Create a Shotgrid Version

        Args:
            version_name(str): The full version name, `code` field in SG.
            instance (pyblish.Instance): The version's Instance.
        
        Returns:
            dict: The newly created Shotgrid Version.
        """
        version_data = {
            "project": instance.data.get("shotgridProject"),
            "entity": instance.data.get("shotgridEntity"),
            "code": version_name,
        }

        if instance.data.get("shotgridTask"):
            version_data["sg_task"] = instance.data["shotgridTask"]

        return instance.context.data["shotgridSession"].create(
            "Version",
            version_data
        )


