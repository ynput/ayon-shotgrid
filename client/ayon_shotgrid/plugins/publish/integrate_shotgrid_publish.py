import os
import re
import platform

import pyblish.api

from ayon_core.pipeline import KnownPublishError
from ayon_core.pipeline.publish import get_publish_repre_path


class IntegrateShotgridPublish(pyblish.api.InstancePlugin):
    """
    Create published Files from representations and add it to version. If
    representation is tagged as shotgrid review, it will add it in
    path to movie for a movie file or path to frame for an image sequence.
    """
    order = pyblish.api.IntegratorOrder + 0.499
    label = "Shotgrid Published Files"

    def process(self, instance):
        # Skip execution if instance is marked to be processed in the farm
        if instance.data.get("farm"):
            self.log.info(
                "Instance is marked to be processed on farm. Skipping")
            return

        sg_session = instance.context.data.get("shotgridSession")
        sg_version = instance.data.get("shotgridVersion")

        if not sg_version:
            return

        for representation in instance.data.get("representations", []):

            if "shotgridreview" not in representation.get("tags", []):
                self.log.debug(
                    "No 'shotgridreview' tag on representation "
                    f"'{representation.get('name')}', skipping."
                )
                continue

            local_path = get_publish_repre_path(
                instance, representation, False
            )

            sg_project = instance.data.get("shotgridProject")
            sg_entity = instance.data.get("shotgridEntity")
            sg_task = instance.data.get("shotgridTask")

            code = os.path.basename(local_path)
            # Extract and remove version number from code so Published file
            # versions are grouped together. More info about this on:
            # https://developer.shotgridsoftware.com/tk-core/_modules/tank/"
            # "util/shotgun/publish_creation.html
            version_number = 0
            match = re.search("_v(\\d+)", code)
            if match:
                version_number = int(match.group(1))
                # Remove version from name
                code = re.sub("_v\\d+", "", code)
                # Remove frames from name
                #   (i.e., filename.1001.exr -> filename.exr)
                code = re.sub("\\.\\d+", "", code)

            query_filters = [
                ["project", "is", sg_project],
                ["entity", "is", sg_entity],
                ["version", "is", sg_version],
                ["code", "is", code],
            ]

            if sg_task:
                query_filters.append(["task", "is", sg_task])

            sg_published_file = sg_session.find_one(
                "PublishedFile",
                query_filters
            )

            if instance.context.data.get("shotgridLocalStorageEnabled"):
                sg_local_storage = sg_session.find_one(
                    "LocalStorage",
                    filters=[
                        [
                            "code",
                            "is",
                            instance.context.data["shotgridLocalStorageKey"]
                        ]
                    ],
                    fields=["mac_path", "windows_path", "linux_path"]
                )

                if not sg_local_storage:
                    raise KnownPublishError(
                        "Unable to find a Local Storage in Shotgrid."
                        "Enable them in Site Preferences > Local Management:"
                        "https://help.autodesk.com/view/SGSUB/ENU/?guid="
                        "SG_Administrator_ar_data_management_ar_linking_"
                        "local_files_html"
                    )

                self.log.debug(f"Using the Local Storage: {sg_local_storage}")

                try:
                    if platform.system() == "Windows":
                        _, file_partial_path = local_path.split(
                            sg_local_storage["windows_path"]
                        )
                        file_partial_path = file_partial_path.replace(
                            "\\", "/")
                    elif platform.system() == "Linux":
                        _, file_partial_path = local_path.split(
                            sg_local_storage["linux_path"]
                        )
                    elif platform.system() == "Darwin":
                        _, file_partial_path = local_path.split(
                            sg_local_storage["mac_path"]
                        )

                    file_partial_path = file_partial_path.lstrip("/")
                except ValueError as exc:
                    raise KnownPublishError(
                        f"Filepath {local_path} doesn't match the "
                        f"Shotgrid Local Storage {sg_local_storage}"
                        "Enable them in Site Preferences > Local Management:"
                        "https://help.autodesk.com/view/SGSUB/ENU/?guid="
                        "SG_Administrator_ar_data_management_ar_linking_local_"
                        "files_html"
                    ) from exc

                path = {
                    "local_storage": sg_local_storage,
                    "relative_path": file_partial_path
                }
            else:
                self.log.info(
                    "Shotgrid Local Storage disabled, using local path.")
                path = {"local_path": local_path}

            published_file_data = {
                "project": sg_project,
                "code": code,
                "entity": sg_entity,
                "version": sg_version,
                "path": path,
                # Add file type and version number fields
                "published_file_type": self._find_published_file_type(
                    instance, local_path, representation
                ),
                "version_number": version_number,
            }

            if sg_task:
                published_file_data["task"] = sg_task

            if not sg_published_file:
                try:
                    sg_published_file = sg_session.create(
                        "PublishedFile",
                        published_file_data
                    )
                except Exception as e:
                    self.log.error(
                        "Unable to create PublishedFile with data: "
                        f"{published_file_data}"
                    )
                    raise e

                self.log.info(
                    f"Created Shotgrid PublishedFile: {sg_published_file}"
                )
            else:
                sg_session.update(
                    sg_published_file["type"],
                    sg_published_file["id"],
                    published_file_data,
                )
                self.log.info(
                    f"Update Shotgrid PublishedFile: {sg_published_file}"
                )

            if instance.data["family"] == "image":
                sg_session.upload_thumbnail(
                    sg_published_file["type"],
                    sg_published_file["id"],
                    local_path
                )
            instance.data["shotgridPublishedFile"] = sg_published_file

    def _find_published_file_type(self, instance, filepath, representation):
        """Given a filepath infer what type of published file type it is."""

        _, ext = os.path.splitext(filepath)
        published_file_type = "Unknown"

        if ext in [".exr", ".jpg", ".jpeg", ".png", ".dpx", ".tif", ".tiff"]:
            is_sequence = len(representation["files"]) > 1
            published_file_type = "Rendered Image" if is_sequence else "Image"
        elif ext in [".mov", ".mp4"]:
            published_file_type = "Movie"
        elif ext == ".abc":
            published_file_type = "Alembic Cache"
        elif ext in [".bgeo", ".sc", ".gz"]:
            published_file_type = "Bgeo Geo"
        elif ext in [".ma", ".mb"]:
            published_file_type = "Maya Scene"
        elif ext == ".nk":
            published_file_type = "Nuke Script"
        elif ext == ".hip":
            published_file_type = "Houdini Scene"
        elif ext in [".hda"]:
            published_file_type = "HDA"
        elif ext in [".fbx"]:
            published_file_type = "FBX Geo"

        filters = [["code", "is", published_file_type]]
        sg_session = instance.context.data.get("shotgridSession")
        sg_published_file_type = sg_session.find_one(
            "PublishedFileType", filters=filters
        )
        if not sg_published_file_type:
            # Create a published file type on the fly
            sg_published_file_type = sg_session.create(
                "PublishedFileType", {"code": published_file_type}
            )
        return sg_published_file_type