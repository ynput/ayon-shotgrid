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
    polling_frequency: str = Field(
        10,
        title="How often (in seconds) to query the Shotgrid Database."
    )


class ShotgridSettings(BaseSettingsModel):
    """Shotgrid addon settings."""

    shotgrid_server: str = Field(
        "",
        title="Shotgrid server url",
    )
    shotgrid_script_name: str = Field(
        "",
        title="Shotgrid Script Name",
    )
    shotgrid_api_key: str = Field(
        "",
        title="Shotgrid API Key"
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
