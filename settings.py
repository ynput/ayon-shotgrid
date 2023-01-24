from pydantic import Field

from ayon_server.settings import BaseSettingsModel

DEFAULT_VALUES = {}


class MySettings(BaseSettingsModel):
    pass
