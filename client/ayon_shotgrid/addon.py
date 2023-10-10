import os

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
        self._shotgrid_script_name = None
        self._shotgrid_api_key = None

    def get_sg_url(self):
        return self._shotgrid_server_url if self._shotgrid_server_url else None

    def get_plugin_paths(self):
        return {
            "publish": [
                os.path.join(SHOTGRID_MODULE_DIR, "plugins", "publish")
            ]
        }

    def create_shotgrid_session(self):
        from .lib import credentials

        sg_username, sg_password = credentials.get_local_login()

        if not sg_username or not sg_password:
            return None

        return credentials.create_sg_session(
            self._shotgrid_server_url,
            sg_username,
            sg_password
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
