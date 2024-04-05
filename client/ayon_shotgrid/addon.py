import os
import ayon_api
from ayon_core.modules import (
    AYONAddon,
    ITrayModule,
    IPluginPaths,
)
from ayon_core.lib import Logger

log = Logger.get_logger(__name__)

SHOTGRID_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))


class ShotgridAddon(AYONAddon, ITrayModule, IPluginPaths):
    name = "shotgrid"
    enabled = True
    tray_wrapper = None

    def initialize(self, studio_settings):
        addon_settings = studio_settings.get(self.name, {})
        log.debug(
            f"Initializing {self.name} module with "
            "settings: {addon_settings}"
        )
        self._shotgrid_server_url = addon_settings.get("shotgrid_server")
        self._client_login_type = addon_settings.get(
            "client_login", {}).get("type")

        sg_secret = ayon_api.get_secret(addon_settings["server_sg_script_key"])
        self._shotgrid_api_key = sg_secret.get("value")
        self._shotgrid_script_name = addon_settings["server_sg_script_name"]

        # reconfigure for client user api key since studio might need to
        # use a different api key with different permissions access
        if self._client_login_type == "tray_api_key":
            self._shotgrid_script_name = (
                addon_settings
                .get("client_login", {})
                .get("tray_api_key", {})
                .get("client_sg_script_name")
            )
            sg_client_secret = ayon_api.get_secret((
                addon_settings
                .get("client_login", {})
                .get("tray_api_key", {})
                .get("client_sg_script_key")
            ))
            self._shotgrid_api_key = sg_client_secret.get("value")

        self._enable_local_storage = addon_settings.get(
            "enable_shotgrid_local_storage")

        # ShotGrid local storage entry name
        self._local_storage_key = addon_settings.get("local_storage_key")

    def get_sg_url(self):
        return self._shotgrid_server_url or None

    def get_sg_script_name(self):
        return self._shotgrid_script_name or None

    def get_sg_api_key(self):
        return self._shotgrid_api_key or None

    def get_client_login_type(self):
        return self._client_login_type or None

    def get_plugin_paths(self):
        return {
            "publish": [
                os.path.join(SHOTGRID_MODULE_DIR, "plugins", "publish")
            ]
        }

    def is_local_storage_enabled(self):
        return self._enable_local_storage or False

    def get_local_storage_key(self):
        return self._local_storage_key or None

    def create_shotgrid_session(self):
        from .lib import credentials
        kwargs = {
            "shotgrid_url": self._shotgrid_server_url,
        }

        proxy = os.environ.get("HTTPS_PROXY", "").lstrip("https://")
        if proxy:
            kwargs["proxy"] = proxy

        if self._client_login_type == "env":
            sg_username = (
                os.getenv("AYON_SG_USERNAME")
                or os.getenv("USER")
            )
            kwargs.update({
                "username": sg_username,
                "api_key": self._shotgrid_api_key,
                "script_name": self._shotgrid_script_name,
            })
        elif self._client_login_type == "tray_pass":
            sg_username, sg_password = credentials.get_local_login()

            if not sg_username or not sg_password:
                return None

            kwargs.update({
                "username": sg_username,
                "password": sg_password
            })

        elif self._client_login_type == "tray_api_key":
            sg_username, _ = credentials.get_local_login()
            kwargs.update({
                "username": sg_username,
                "api_key": self._shotgrid_api_key,
                "script_name": self._shotgrid_script_name,
            })

        return credentials.create_sg_session(**kwargs)

    def tray_init(self):
        # do not initialize tray if client login type is not tray related
        if self._client_login_type == "env":
            return

        from .tray.shotgrid_tray import ShotgridTrayWrapper
        self.tray_wrapper = ShotgridTrayWrapper(self)

    def tray_start(self):
        # do not initialize tray if client login type is not tray related
        if self._client_login_type == "env":
            return

        return self.tray_wrapper.set_username_label()

    def tray_exit(self, *args, **kwargs):
        # do not initialize tray if client login type is not tray related
        if self._client_login_type == "env":
            return

        return self.tray_wrapper

    def tray_menu(self, tray_menu):
        # do not initialize tray if client login type is not tray related
        if self._client_login_type == "env":
            return

        return self.tray_wrapper.tray_menu(tray_menu)
