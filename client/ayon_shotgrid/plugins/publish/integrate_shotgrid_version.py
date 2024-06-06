from pprint import pformat
import re

import pyblish.api

from ayon_core.pipeline.publish import get_publish_repre_path
from ayon_core.lib.transcoding import (
    VIDEO_EXTENSIONS,
    IMAGE_EXTENSIONS
)


class IntegrateShotgridVersion(pyblish.api.InstancePlugin):
    """Integrate Shotgrid Version"""
    order = pyblish.api.IntegratorOrder + 0.497
    label = "Shotgrid Version"

    # Dictionary of SG fields we want to update that map to other fields in the
    # Ayon entity
    fields_to_add = {
        "comment": (str, "description"),
        "productType": (str, "sg_version_type"),
    }

    def process(self, instance):

        # Skip execution if instance is marked to be processed in the farm
        if instance.data.get("farm"):
            self.log.info(
                "Instance is marked to be processed on farm. Skipping")
            return

        context = instance.context

        # Dictionary that holds all the data we want to set/update on
        # the corresponding SG version
        data_to_update = {}

        intent = context.data.get("intent")
        if intent:
            data_to_update["sg_status_list"] = intent["value"]

        # find thumbnail path
        thumbnail_path = instance.data.get("thumbnailPath")

        found_reviewable = False
        for representation in instance.data.get("representations", []):
            self.log.debug(pformat(representation))

            if "shotgridreview" not in representation.get("tags", []):
                continue

            local_path = get_publish_repre_path(
                instance, representation, False
            )

            if f".{representation['ext']}" in VIDEO_EXTENSIONS:
                found_reviewable = True
                data_to_update["sg_path_to_movie"] = local_path
                if (
                    "slate" in instance.data["families"]
                    and "slate-frame" in representation["tags"]
                ):
                    data_to_update["sg_movie_has_slate"] = True

            elif f".{representation['ext']}" in IMAGE_EXTENSIONS:
                found_reviewable = True
                # Replace the frame number with '%04d'
                path_to_frame = re.sub(r"\.\d+\.", ".%04d.", local_path)

                data_to_update |= {
                    "sg_path_to_movie": path_to_frame,
                    "sg_path_to_frames": path_to_frame,
                }

                if "slate" in instance.data["families"]:
                    data_to_update["sg_frames_have_slate"] = True

        if not found_reviewable and thumbnail_path is not None:
            # create a thumbnail data to update
            found_reviewable = True
            data_to_update |= {
                "sg_path_to_movie": thumbnail_path,
                "sg_path_to_frames": thumbnail_path,
            }

        # If there's no data to set/update, skip creation of SG version
        if not found_reviewable:
            self.log.info(
                "No data to integrate to SG for product name "
                f"'{instance.data['productName']}', skipping "
                "version creation."
            )
            return

        sg_session = context.data["shotgridSession"]

        # TODO: Use path template solver to build version code from settings
        anatomy_data = instance.data.get("anatomyData", {})
        version_name_tokens = [
            anatomy_data["folder"]["name"],
            instance.data["productName"],
        ]

        if instance.data["shotgridTask"]:
            version_name_tokens.append(
                instance.data["shotgridTask"]["content"]
            )

        version_name_tokens.append(
            "v{:03}".format(int(anatomy_data["version"]))
        )

        version_name = "_".join(version_name_tokens)

        self.log.info(
            f"Integrating Shotgrid version with code: {version_name}")

        sg_version = self._find_existing_version(version_name, instance)
        if not sg_version:
            sg_version = self._create_version(version_name, instance)
            self.log.info(f"Create Shotgrid version: {sg_version}")
        else:
            self.log.info(f"Use existing Shotgrid version: {sg_version}")

        # Upload movie to version
        path_to_movie = data_to_update.get("sg_path_to_movie")
        if path_to_movie:
            self.log.info(
                "Upload review: {} for version shotgrid {}".format(
                    path_to_movie, sg_version.get("id")
                )
            )
            sg_session.upload(
                "Version",
                sg_version.get("id"),
                path_to_movie,
                field_name="sg_uploaded_movie",
            )

        # Update frame start/end on the version
        frame_start = instance.data.get(
            "frameStart", context.data.get("frameStart"))
        handle_start = instance.data.get(
            "handleStart", context.data.get("handleStart"))
        if frame_start is not None and handle_start is not None:
            frame_start = int(frame_start)
            handle_start = int(handle_start)
            data_to_update["sg_first_frame"] = frame_start - handle_start

        frame_end = instance.data.get(
            "frameEnd", context.data.get("frameEnd"))
        handle_end = instance.data.get(
            "handleEnd", context.data.get("handleEnd"))
        if frame_end is not None and handle_end is not None:
            frame_end = int(frame_end)
            handle_end = int(handle_end)
            data_to_update["sg_last_frame"] = frame_end + handle_end

        # Add a few extra fields from AY to SG version
        for ay_field, sg_field in self.fields_to_add.items():
            field_value = (
                instance.data.get(ay_field) or context.data.get(ay_field))
            if field_value:
                # Break sg_field tuple into whatever type of data it
                # is and its name
                type_, field_name = sg_field

                data_to_update[field_name] = type_(field_value)

        # Add version objectId to "sg_ayon_id" so we can keep a link
        # between both
        version_id = instance.data.get("versionEntity", {}).get("id")
        if not version_id:
            self.log.warning(
                "Instance doesn't have a 'versionEntity' to extract the id."
            )
            version_id = "-"
        data_to_update["sg_ayon_id"] = str(version_id)

        self.log.info(f"Updating Shotgrid version with {data_to_update}")
        sg_session.update("Version", sg_version["id"], data_to_update)

        instance.data["shotgridVersion"] = sg_version
        self.log.debug(f"Shotgrid version: {sg_version}")

    def _find_existing_version(self, version_name, instance):
        """Find if a Version already exists in ShotGrid.

        Args:
            version_name(str): The full version name, `code` field in SG.
            instance (pyblish.Instance): The version's Instance.

        Returns:
            dict/None: A ShotGrid Version or None if there is none.
        """
        filters = [
            ["project", "is", instance.data.get("shotgridProject")],
            ["entity", "is", instance.data.get("shotgridEntity")],
            ["code", "is", version_name],
        ]

        if instance.data.get("shotgridTask"):
            filters.append(
                ["sg_task", "is", instance.data.get("shotgridTask")])

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
