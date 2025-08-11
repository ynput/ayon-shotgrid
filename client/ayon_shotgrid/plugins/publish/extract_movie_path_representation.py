import pyblish.api

from ayon_core.lib import filter_profiles
from ayon_shotgrid import MoviePathTrait


class ExtractMoviePath(pyblish.api.InstancePlugin):
    """Looks for representation to be marked for source of sg_path_to_movie"""
    order = pyblish.api.ExtractorOrder + 0.45
    label = "Extract trait for representation for sg_path_to_movie"
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

        traits = {}
        repre_names = [
            repre["name"]
            for repre in instance.data.get("representations", [])
        ]
        for profile_repre_name in profile["repre_names"]:
            self.log.debug(
                f"Looking for representation `{profile_repre_name}`")
            if profile_repre_name in repre_names:
                self.log.debug(
                    f"Adding MoviePathTrait for `{profile_repre_name}`")
                traits[profile_repre_name] = MoviePathTrait()
                break

        if traits:
            instance.data["traits"] = traits

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
