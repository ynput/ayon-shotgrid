import os

import ayon_api

from openpype.modules import (
    OpenPypeModule,
    IPluginPaths,
)

SHOTGRID_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))


class ShotgridAddon(OpenPypeModule, IPluginPaths):
    name = "shotgrid"
    enabled = True

    def initialize(self, modules_settings):
        module_settings = modules_settings.get(self.name, dict())
        self._shotgrid_server_url = module_settings.get("shotgrid_server")
        sg_secret = ayon_api.get_secret(module_settings["shotgrid_api_secret"])
        self._shotgrid_script_name = sg_secret.get("name")
        self._shotgrid_api_key = sg_secret.get("value")
        self._enable_local_storage = module_settings.get("enable_shotgrid_local_storage")
        self._local_storage_key = module_settings.get("local_storage_key")

    def get_sg_url(self):
        return self._shotgrid_server_url if self._shotgrid_server_url else None

    def get_sg_script_name(self):
        return self._shotgrid_script_name if self._shotgrid_script_name else None

    def get_sg_api_key(self):
        return self._shotgrid_api_key if self._shotgrid_api_key else None

    def get_plugin_paths(self):
        return {
            "publish": [
                os.path.join(SHOTGRID_MODULE_DIR, "plugins", "publish")
            ]
        }

    def is_local_storage_enabled(self):
        return self._enable_local_storage if self._enable_local_storage else False

    def get_local_storage_key(self):
        return self._local_storage_key if self._local_storage_key else None

    def create_shotgrid_session(self):
        from .lib import credentials

        sg_username = os.getenv("AYON_SG_USERNAME") or os.getenv("USER")
        proxy = os.environ.get("HTTPS_PROXY", "").lstrip("https://")

        return credentials.create_sg_session(
            self._shotgrid_server_url,
            sg_username,
            self._shotgrid_script_name,
            self._shotgrid_api_key,
            proxy,
        )
