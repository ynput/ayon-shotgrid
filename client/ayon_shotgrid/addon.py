import os

from .lib import credentials

from openpype.modules import (
    OpenPypeModule,
    ITrayModule,
    IPluginPaths,
)

SHOTGRID_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))


class ShotgridAddon(OpenPypeModule, ITrayModule, IPluginPaths):
    name = "shotgrid"
    enabled = True
    tray_wrapper = None

    def initialize(self, modules_settings):
        module_settings = modules_settings.get(self.name, dict())
        self._shotgrid_server_url = module_settings.get("shotgrid_server")
        self._shotgrid_script_name = module_settings.get("shotgrid_script_name")
        self._shotgrid_api_key = module_settings.get("shotgrid_api_key")

    def get_sg_url(self):
        return self._shotgrid_server_url if self._shotgrid_server_url else None

    def get_plugin_paths(self):
        return {
            "publish": [
                os.path.join(SHOTGRID_MODULE_DIR, "plugins", "publish")
            ]
        }

    def create_shotgrid_session(self, username):
        from .lib import credentials

        return credentials.create_sg_session(
            self._shotgrid_server_url,
            self._shotgrid_script_name,
            self._shotgrid_api_key,
            username
        )

    def tray_init(self):
        from .tray.shotgrid_tray import ShotgridTrayWrapper
        self.tray_wrapper = ShotgridTrayWrapper(self)

    def tray_start(self):
        return self.tray_wrapper.set_username_label()

    def tray_exit(self, *args, **kwargs):
        return self.tray_wrapper

    def tray_menu(self, tray_menu):
        return self.tray_wrapper.tray_menu(tray_menu)
