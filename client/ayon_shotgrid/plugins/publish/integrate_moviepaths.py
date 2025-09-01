import os
import re
from typing import Dict, Any

import ayon_api
import pyblish.api

from ayon_core.lib import filter_profiles
from ayon_core.addon import AddonsManager


class IntegrateMoviePath(pyblish.api.InstancePlugin):
    """Looks for representation to be marked for source of sg_path_to_movie

    Dispatches event to update synchronized Version paths to limit race
    conditions.

    Must be called after full `Integrate` when both Version and Representations
    are present in DB.
    """

    order = pyblish.api.IntegratorOrder + 0.45
    label = "Integrate event for Flow movie paths"
    settings_category = "shotgrid"

    profiles = []

    def process(self, instance: pyblish.api.Instance):
        product_type = instance.data["productType"]

        if instance.data.get("farm"):
            self.log.debug(
                f"`{product_type}` should be processed on farm, skipping."
            )
            return

        published_representations = instance.data.get(
            "published_representations"
        )
        if not published_representations:
            self.log.debug("Instance does not have published representations")
            return

        preferred_representation = self._get_preferred_representation(
            instance,
            published_representations
        )

        version_entity = instance.data["versionEntity"]
        has_slate = "slate" in version_entity["attrib"]["families"]
        flow_data = self._add_paths(
            published_representations, preferred_representation, has_slate
        )
        if not flow_data:
            return

        self._trigger_event(instance, flow_data)

    def _get_representation_profile(self, instance: pyblish.api.Instance):
        host_name = instance.context.data["hostName"]
        product_type = instance.data["productType"]
        task_name = None
        task_type = None
        task_entity = instance.data.get("taskEntity")
        if task_entity:
            task_type = task_entity["taskType"]
            task_name = task_entity["name"]

        profile = filter_profiles(
            self.profiles,
            {
                "host_names": host_name,
                "product_types": product_type,
                "task_names": task_name,
                "task_types": task_type,
            },
            logger=self.log,
        )
        return profile

    def _get_preferred_representation(
        self,
        instance: pyblish.api.Instance,
        published_representations: Dict[str, Any]
    ):
        profile = self._get_representation_profile(instance)
        if not profile:
            return None

        repre_dict = {
            repre_info["representation"]["name"]: repre_info["representation"]
            for repre_info in published_representations.values()
        }

        for profile_repre_name in profile["repre_names"]:
            self.log.debug(
                f"Looking for representation `{profile_repre_name}`"
            )
            preferred_representation = repre_dict.get(profile_repre_name)
            if preferred_representation:
                self.log.debug(
                    f"Using `{profile_repre_name}` as source for sg_movie_path"
                )
                return preferred_representation

    def _add_paths(
        self,
        published_representations: Dict[str, Any],
        preferred_representation: Dict[str, Any],
        has_slate: bool
    ):
        """Adds local path to review file to `sg_path_to_*` as metadata.

        We are storing local paths for external processing, some studios might
        have tools to handle review files in another processes.
        """
        thumbnail_path = None
        found_representation = False

        for repre_info in published_representations.values():
            representation = repre_info["representation"]
            local_path = representation["attrib"]["path"]
            local_path = os.path.normpath(local_path)

            representation_name = representation["name"]
            if (preferred_representation and
                    representation_name == preferred_representation["name"]):
                found_representation = preferred_representation
                break

            if representation_name == "thumbnail":
                thumbnail_path = local_path
                continue

            if not representation_name.startswith("review"):
                continue

        flow_data = {}
        if found_representation:
            # clunky guess, not having access to ayon_core.VIDEO_EXTENSIONS
            if len(found_representation["files"]) == 1:
                flow_data["sg_path_to_movie"] = local_path
            else:
                # Replace the frame number with '###'
                n = 0
                match = re.search(r"\.(\d+)\.", local_path)
                if match:
                    digit_str = match.group(1)
                    n = len(digit_str)
                path_to_frame = re.sub(r"\.\d+\.", f".{n*'#'}.", local_path)

                flow_data.update(
                    {
                        "sg_path_to_movie": path_to_frame,
                        "sg_path_to_frames": path_to_frame,
                    }
                )

            if has_slate:
                flow_data["sg_frames_have_slate"] = True

        elif thumbnail_path:
            flow_data.update({
                "sg_path_to_movie": thumbnail_path,
                "sg_path_to_frames": thumbnail_path,
            })

        return flow_data

    def _trigger_event(
        self,
        instance: pyblish.api.Instance,
        flow_data: Dict[str, Any]
    ):
        """Triggers event to update media path on Flow(SG) Version

        Temporarily via addon server endpoint to mitigate bug in
        enroll_event_job.ignore_sender_types. When resolved could be changed
        to simple dispatch_event.
        """

        project_name = instance.context.data["projectName"]
        version_id = instance.data["versionEntity"]["id"]
        flow_data["versionId"] = version_id

        self.log.debug(f"Sending event for {version_id} with {flow_data}")

        addon = AddonsManager().get("shotgrid")
        if not addon:
            self.log.warning("No addon found, couldn't send event")
            return

        endpoint = f"{addon.get_server_addon_endpoint}/{project_name}/trigger_mediapath"  # noqa: E501
        response = ayon_api.post(
            endpoint,
            **flow_data,
        )
        response.raise_for_status("Cannot trigger update of media paths.")
