import pyblish.api

from ayon_api import update_representation

from ayon_shotgrid import MoviePathTrait


class IntegrateMoviePath(pyblish.api.InstancePlugin):
    """Persists MoviePath trait to selected representation.

    Marks if there is specific representation that should be used to fill
    Version.sg_path_to_movie instead of review|thumbnail by default.
    """
    # must be before IntegrateAYONReview
    order = pyblish.api.IntegratorOrder + 0.001
    label = "Integrate trait for SG"

    def process(self, instance):
        product_type = instance.data["productType"]
        if instance.data.get("farm"):
            self.log.debug(f"`{product_type}` should be processed on "
                           f"farm, skipping.")
            return

        traits = instance.data.get("traits")
        if not traits:
            self.log.debug(f"Instance `{product_type}` does not have traits")
            return

        project_name = instance.context.data["projectName"]

        published_representations = instance.data.get(
            "published_representations", []
        )
        for repre_id, repre_info in published_representations.items():
            repre_name = repre_info["representation"]["name"]
            trait = traits.get(repre_name)
            if not trait:
                continue

            if trait.id != MoviePathTrait.id:
                continue

            self.log.debug(
                f"Adding trait for product type `{product_type}` - "
                f"representation`{repre_name}`"
            )
            update_representation(
                project_name,
                repre_id,
                traits={ trait.id: trait.as_dict() }
            )
