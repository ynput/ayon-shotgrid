from pydantic import Field

from ayon_server.settings import BaseSettingsModel

from .service_handlers import (
    ShotgridServiceHandlers,
    DEFAULT_SERVICE_HANDLERS_SETTINGS,
)


class ShotgridServiceSettings(BaseSettingsModel):
    """Shotgrid service cares about handling shotgrid event and synchronization.

    To be able do that work it is required to listen and process events as one
    of shotgrid users. It is recommended to use special user for that purposes
    so you can see which changes happened from service.
    """

    username: str = Field(
        "",
        title="Shotgrid Script Name",
    )
    api_key: str = Field(
        "",
        title="Shotgrid API Key"
    )


class ShotgridSettings(BaseSettingsModel):
    """Shotgrid addon settings."""

    shotgrid_server: str = Field(
        "",
        title="Shotgrid server url",
    )

    service_event_handlers: ShotgridServiceHandlers = Field(
        default_factory=ShotgridServiceHandlers,
        title="Server Actions/Events",
    )

    service_settings: ShotgridServiceSettings = Field(
        default_factory=ShotgridServiceSettings,
        title="Service settings",
    )


DEFAULT_VALUES = {
    "shotgrid_server": "",
    "service_event_handlers": DEFAULT_SERVICE_HANDLERS_SETTINGS,
    "service_settings": {
        "username": "",
        "api_key": ""
    },
}
