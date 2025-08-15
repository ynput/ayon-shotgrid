import pyblish.api

from ayon_core.lib import filter_profiles


class ExtractMoviePath(pyblish.api.InstancePlugin):
    """Looks for representation to be marked for source of sg_path_to_movie

    Uses representation["data"] instead of Traits as generic `Integrate` causes
    race condition.

    Todo: Should be refactored to traits when everything is moved to traits.
    """
    order = pyblish.api.ExtractorOrder + 0.45
    label = "Extract mark for representation for sg_path_to_movie"
    settings_category = "shotgrid"

    profiles = []

    def process(self, instance):
        product_type = instance.data["productType"]

        if instance.data.get("farm"):
            self.log.debug(
                f"`{product_type}` should be processed on farm, skipping."
            )
            return

        profile = self._get_representation_profile(instance)
        if not profile:
            self.log.debug(
                (
                    f"Skipped instance `{product_type}`. None of profiles "
                    f"matched in presets."
                )
            )
            return

        repre_dict = {
            repre["name"]: repre
            for repre in instance.data.get("representations", [])
        }
        for profile_repre_name in profile["repre_names"]:
            self.log.debug(
                f"Looking for representation `{profile_repre_name}`")
            found_repre = repre_dict.get(profile_repre_name)
            if found_repre:
                self.log.debug(
                    f"Adding SG_use_as_movie_path for `{profile_repre_name}`")
                flow_data = found_repre.setdefault("data", {}).setdefault("flow", {})
                flow_data["use_as_movie_path"] = True
                break

    def _get_representation_profile(self, instance):
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
                "hosts": host_name,
                "product_types": product_type,
                "task_names": task_name,
                "task_types": task_type,
            },
            logger=self.log,
        )
        return profile
