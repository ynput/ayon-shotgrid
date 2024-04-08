from ayon_server.settings import BaseSettingsModel, SettingsField
from ayon_server.settings.enum import secrets_enum


class ShotgridServiceSettings(BaseSettingsModel):
    """Specific settings for the Shotgrid Services: Processor, Leecher and
    Transmitter.

    The different services process events from either Shotgrid or AYON,
    this field allows to control how long to wait between each event
    is processed.
    """
    polling_frequency: int = SettingsField(
        default=10,
        title="How often (in seconds) to process Shotgrid related events.",
        validate_default=False,
    )

    ayon_service_user: str = SettingsField(
        default="service",
        title="AYON service user",
        description="The AYON user used in the services (the user corresponding to the `AYON_API_KEY` set in the service)",
    )

    script_key: str = SettingsField(
        default="",
        enum_resolver=secrets_enum,
        title="ShotGrid's Script api key",
        description=(
            "Ayon Secret used for Service related server operations "
            "Secret should lead to ShotGrid's Script api key. "
            "See more at: https://developer.shotgridsoftware.com/python-api/"
            "authentication.html#setting-up-shotgrid"
        ),
    )

    script_name: str = SettingsField(
        default="",
        placeholder="Create and Paste a script name here",
        title="ShotGrid's Script Name",
        description=(
            "Ayon Secret used for Service related server operations "
            "Secret should lead to ShotGrid's Script Name. "
            "See more at: https://developer.shotgridsoftware.com/python-api/"
            "authentication.html#setting-up-shotgrid"
        ),
    )


class ClientLoginDetailsModel(BaseSettingsModel):
    _layout = "expanded"

    client_sg_script_key: str = SettingsField(
        default="",
        placeholder="Create and Paste a script api key here",
        title="Client related ShotGrid's Script api key",
        description=(
            "Ayon Secret used for Client related user operations "
            "Secret should lead to ShotGrid's Script api key. "
            "See more at: https://developer.shotgridsoftware.com/python-api/"
            "authentication.html#setting-up-shotgrid"
        ),
    )
    client_sg_script_name: str = SettingsField(
        default="",
        placeholder="Create and Paste a script name here",
        title="Client related ShotGrid's Script Name",
        description=(
            "Ayon Secret used for Client related user operations "
            "Secret should lead to ShotGrid's Script Name. "
            "See more at: https://developer.shotgridsoftware.com/python-api/"
            "authentication.html#setting-up-shotgrid"
        ),
    )


client_login_types_enum = [
    {"value": "env", "label": "Via Environment Variables"},
    {"value": "tray_pass", "label": "Via Tray App with password"},
    {"value": "tray_api_key", "label": "Via Tray App with shared api key"},
]


class ClientLoginModel(BaseSettingsModel):
    _layout = "expanded"

    type: str = SettingsField(
        "env",
        title="Client login type",
        description="Switch between client login types",
        enum_resolver=lambda: client_login_types_enum,
        conditionalEnum=True
    )

    tray_api_key: ClientLoginDetailsModel = SettingsField(
        default_factory=ClientLoginDetailsModel,
        title="Tray App",
        scope=["studio"],
    )

    env: ClientLoginDetailsModel = SettingsField(
        default_factory=ClientLoginDetailsModel,
        title="Environment Variables",
        scope=["studio"],
    )


class ShotgridSettings(BaseSettingsModel):
    """Shotgrid integration settings.

    Main setting for the AYON x Shotgrid integration, these need to be filled out
    in order to for the services to correctly operate.
    """

    shotgrid_server: str = SettingsField(
        default="",
        title="Shotgrid URL",
        description="The URL to the Shotgrid Server we want to interact with.",
        example="https://my-site.shotgrid.autodesk.com",
        scope=["studio"]
    )
    server_sg_script_key: str = SettingsField(
        default="",
        enum_resolver=secrets_enum,
        title="Shotgrid API Script key",
        description=(
            "Ayon Secret used for Server and Services related  operations "
            "Secret should lead to ShotGrid's Script api key. "
            "See more at: https://developer.shotgridsoftware.com/python-api/"
            "authentication.html#setting-up-shotgrid"
        ),
        scope=["studio"],
        section="---",
    )
    server_sg_script_name: str = SettingsField(
        default="",
        placeholder="Create and Paste a script name here",
        title="Shotgrid API Script Name",
        description=(
            "Server and Services related  operations "
            "Secret should lead to ShotGrid's Script Name. "
            "See more at: https://developer.shotgridsoftware.com/python-api/"
            "authentication.html#setting-up-shotgrid"
        ),
        scope=["studio"]
    )
    client_login: ClientLoginModel = SettingsField(
        default_factory=ClientLoginModel,
        title="Client login settings",
        scope=["studio"],
        section="---",
    )
    shotgrid_project_code_field: str = SettingsField(
        default="code",
        title="Shotgrid Project Code field name",
        description="In order to create AYON projects, we need a Project Code, you can specify here which field in the Shotgrid Project entitiy represents it.",
        example="sg_code"
    )
    enable_shotgrid_local_storage: bool = SettingsField(
        default=True,
        title="Enable Shotgrid Local Storage.",
        description="Whether to try make use of local storage defined in Shotgrid ('Site Preferences -> File Management -> Local Storage') or not.",
        scope=["studio"],
    )
    shotgrid_local_storage_key: str = SettingsField(
        default="primary",
        title="Shotgrid Local Storage entry name",
        description="Name of the 'code' to select which one of the multiple possible local storages entries to use.",
        example="ayon_storage",
        scope=["studio"],
    )
    service_settings: ShotgridServiceSettings = SettingsField(
        default_factory=ShotgridServiceSettings,
        title="Service settings",
        scope=["studio"],
    )
