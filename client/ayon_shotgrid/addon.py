import os

from ayon_core.addon import (
    AYONAddon,
    IPluginPaths,
    ITraits,
)
from ayon_core.lib import Logger
from ayon_core.pipeline.traits import TraitBase

from .version import __version__

log = Logger.get_logger(__name__)

SHOTGRID_ADDON_DIR = os.path.dirname(os.path.abspath(__file__))


class ShotgridAddon(AYONAddon, IPluginPaths, ITraits):
    name = "shotgrid"
    version = __version__

    def initialize(self, studio_settings):
        addon_settings = studio_settings[self.name]

        log.debug(
            f"Initializing {self.name} addon with "
            "settings: {addon_settings}"
        )
        self._shotgrid_server_url = addon_settings["shotgrid_server"]

        self._shotgrid_api_key = None
        self._shotgrid_script_name = None

        self._enable_local_storage = addon_settings.get(
            "enable_shotgrid_local_storage")

        # ShotGrid local storage entry name
        self._local_storage_key = addon_settings.get(
            "shotgrid_local_storage_key")

    def get_sg_url(self):
        return self._shotgrid_server_url or None

    def get_sg_script_name(self):
        return self._shotgrid_script_name or None

    def get_sg_api_key(self):
        return self._shotgrid_api_key or None


    def get_plugin_paths(self):
        return {
            "publish": [
                os.path.join(SHOTGRID_ADDON_DIR, "plugins", "publish")
            ]
        }

    def is_local_storage_enabled(self):
        return self._enable_local_storage or False

    def get_local_storage_key(self):
        return self._local_storage_key or None

    def get_addon_traits(self):
        return [
            MoviePathTrait,
        ]

    @property
    def get_server_addon_endpoint(self, *args: str) -> str:
        parts = ["addons", self.name, self.version]
        parts.extend(args)
        return "/".join(parts)


class MoviePathTrait(TraitBase):
    id = "shotgrid.moviepath.v1"
    name = "Use as sg_path_to_movie"
    description = (
        "This marks representation which publish path should be used"
        "in sg_path_to_movie"
    )
    persistent = True
