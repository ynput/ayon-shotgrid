import os
import pyblish.api

from openpype.pipeline.publish import get_publish_repre_path


class IntegrateShotgridPublish(pyblish.api.InstancePlugin):
    """
    Create published Files from representations and add it to version. If
    representation is tagged as shotgrid review, it will add it in
    path to movie for a movie file or path to frame for an image sequence.
    """
    order = pyblish.api.IntegratorOrder + 0.499
    label = "Shotgrid Published Files"

    def process(self, instance):
        sg_session = instance.context.data.get("shotgridSession")
        sg_version = instance.data.get("shotgridVersion")

        if not sg_version:
            return

        for representation in instance.data.get("representations", []):

            local_path = get_publish_repre_path(
                instance, representation, False
            )

            if representation.get("tags", []):
                continue

            code = os.path.basename(local_path)

            query_filters = [
                ["project", "is", instance.data.get("shotgridProject")],
                ["entity", "is", instance.data.get("shotgridEntity")],
                ["version", "is", sg_version],
                ["code", "is", code],
            ]

            if instance.data.get("shotgridTask"):
                query_filters.append(["task", "is", instance.data.get("shotgridTask")])

            sg_published_file = sg_session.find_one(
                "PublishedFile",
                query_filters
            )

            published_file_data = {
                "project": instance.data.get("shotgridProject"),
                "code": code,
                "entity": instance.data.get("shotgridEntity"),
                "version": sg_version,
                "path": {"local_path": local_path},
            }

            if instance.data.get("shotgridTask"):
                published_file_data["task"] = instance.data.get("shotgridTask")

            if not sg_published_file:
                try:
                    sg_published_file = sg_session.create(
                        "PublishedFile",
                        published_file_data
                    )
                except Exception as e:
                    self.log.error(
                        "Unable to create PublishedFile with data: {}".format(
                            published_file_data
                        )
                    )
                    raise e

                self.log.info(
                    "Created Shotgrid PublishedFile: {}".format(sg_published_file)
                )
            else:
                sg_session.update(
                    sg_published_file["type"],
                    sg_published_file["id"],
                    sg_published_file_data,
                )
                self.log.info(
                    "Update Shotgrid PublishedFile: {}".format(sg_published_file)
                )

            if instance.data["family"] == "image":
                sg_session.upload_thumbnail(
                    sg_published_file["type"], sg_published_file["id"], local_path
                )
            instance.data["shotgridPublishedFile"] = sg_published_file

