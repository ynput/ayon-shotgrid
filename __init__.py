from typing import Type

from ayon_server.addons import BaseServerAddon

from .settings import MySettings, DEFAULT_VALUES
from .version import __version__


class MyAddon(BaseServerAddon):
    name = ""
    title = ""
    version = __version__
    settings_model: Type[MySettings] = MySettings

    async def get_default_settings(self):
        settings_model_cls = self.get_settings_model()
        return settings_model_cls(**DEFAULT_VALUES)
