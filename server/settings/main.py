from pydantic import Field

from ayon_server.settings import BaseSettingsModel
from ayon_server.settings.enum import secrets_enum
from ayon_server.graphql.resolvers.users import get_users


class ShotgridServiceSettings(BaseSettingsModel):
    """Specific settings for the Shotgrid Services: Processor, Leecher and Transmitter.

   The different services process events from either Shotgrid or AYON, this field
   allows to control how long to wait between each event is processed.
    """
    polling_frequency: int = Field(
        default=10,
        title="How often (in seconds) to process Shotgrid related events.",
        validate_default=False,
    )

    ayon_service_user: str = Field(
        default="service",
        title="The AYON Shotgird user",
        description="The AYON user used in the services (the user corresponding to the `AYON_API_KEY` set in the service)",
    )


class ShotgridSettings(BaseSettingsModel):
    """Shotgrid integration settings.

    Main setting for the AYON x Shotgrid integration, these need to be filled out
    in order to for the services to correctly operate.
    """

    shotgrid_server: str = Field(
        default="",
        title="Shotgrid URL",
        description="The URL to the Shotgrid Server we want to interact with.",
        example="https://my-site.shotgrid.autodesk.com"
    )
    shotgrid_api_secret: str = Field(
        default="",
        enum_resolver=secrets_enum,
        title="Shotgrid API Secret",
        description="An AYON Secret where the key is the `script_name` and the value is the `api_key` from Shotgrid. See more at: https://developer.shotgridsoftware.com/python-api/authentication.html#setting-up-shotgrid"
    )
    shotgrid_project_code_field: str = Field(
        default="code",
        title="Shotgrid Project Code field name",
        description="In order to create AYON projects, we need a Project Code, you can specify here which field in the Shotgrid Project entitiy represents it.",
        excample="sg_code"
    )
    service_settings: ShotgridServiceSettings = Field(
        default_factory=ShotgridServiceSettings,
        title="Service settings",
    )

