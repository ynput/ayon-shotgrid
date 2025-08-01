import pyblish.api

from ayon_api import update_representation

from ayon_shotgrid import MoviePathTrait


class IntegrateMoviePath(pyblish.api.InstancePlugin):
    """Persists MoviePath trait to selected representation.

    Marks if there is specific representation that should be used to fill
    Version.sg_movie_path instead of review|thumbnail by default.
    """
    order = pyblish.api.IntegratorOrder + 0.45
    label = "Integrate trait for SG"
    targets = ["local"]

    def process(self, instance):
        traits = instance.data.get("traits")
        if not traits:
            self.log.debug("Instance does not have traits")
            return

        project_name = instance.context.data["projectName"]

        published_representations = instance.data.get(
            "published_representations", []
        )
        for repre_id, repre_info in published_representations.items():
            trait = traits.get(repre_info["representation"]["name"])
            if not trait:
                continue

            if trait.id != MoviePathTrait.id:
                continue

            update_representation(
                project_name,
                repre_id,
                traits={ trait.id: trait.as_dict() }
            )
