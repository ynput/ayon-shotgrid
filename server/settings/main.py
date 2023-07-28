from pydantic import Field

from ayon_server.settings import BaseSettingsModel


class ShotgridServiceSettings(BaseSettingsModel):
    """Shotgrid service cares about handling shotgrid event and synchronization.

    To be able do that work it is required to listen and process events as one
    of shotgrid users. It is recommended to use special user for that purposes
    so you can see which changes happened from service.
    """
    polling_frequency: int = Field(
        10,
        title="How often (in seconds) to query the Shotgrid Database.",
        validate_default=False,
    )

    projects_to_leech: str = Field(
        "",
        title="Project Codes we want to leech (Comma separated list).",
    )


class ShotgridSettings(BaseSettingsModel):
    """Shotgrid addon settings."""

    shotgrid_server: str = Field(
        "",
        title="Shotgrid server url ",
    )
    shotgrid_script_name: str = Field(
        "",
        title="Shotgrid Script Name",
    )
    shotgrid_api_key: str = Field(
        "",
        title="Shotgrid API Key"
    )
    shotgrid_project_code_field: str = Field(
        "",
        title="Shotgrid field for the Project Code"
    )
    service_settings: ShotgridServiceSettings = Field(
        default_factory=ShotgridServiceSettings,
        title="Service settings",
    )


DEFAULT_VALUES = {
    "shotgrid_server": "",
    "shotgrid_script_name": "ayon_connector",
    "shotgrid_project_code_field": "code",
}

