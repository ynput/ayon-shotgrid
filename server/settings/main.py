from ayon_server.entities.core.attrib import attribute_library
from ayon_server.settings import BaseSettingsModel, SettingsField
from ayon_server.settings.enum import secrets_enum, anatomy_presets_enum


def default_shotgrid_entities():
    """The entity types that exist in ShotGrid."""
    return [
        "Project",
        "Episode",
        "Sequence",
        "Scene",
        "Shot",
        "Asset",
        "Task",
        "Version",
    ]


def default_shotgrid_enabled_entities():
    """The entity types in ShotGrid that are enabled by default in AYON."""
    return [
        "Project",
        "Episode",
        "Sequence",
        "Shot",
        "Asset",
        "Task",
        "Version",
    ]


def get_default_folder_attributes():
    """Get AYON's Folder attributes

    Get all the `attribs` for Folder entities in a list
    to be consumed by the `default_factory` in the
    `ShotgridCompatibilitySettings.custom_attribs_map`
    settings.
    """
    attributes = []

    for attr_dict in attribute_library.data.get("folder", {}):
        attr_name = attr_dict["name"]

        if attr_name in ["shotgridId", "shotgridType", "tools"]:
            continue

        attr_map = {
            "ayon": attr_name,
            "sg": "",
            "type": attr_dict["type"],
            "scope": default_shotgrid_enabled_entities()
        }

        if attr_map not in attributes:
            attributes.append(attr_map)

    return attributes


class ShotgridServiceSettings(BaseSettingsModel):
    """Specific settings for the Shotgrid Services: Processor, Leecher and
    Transmitter.

    The different services process events from either Shotgrid or AYON,
    this field allows to control how long to wait between each event
    is processed.
    """
    polling_frequency: int = SettingsField(
        default=10,
        title="How often (in seconds) to process ShotGrid related events.",
        validate_default=False,
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


class AttributesMappingModel(BaseSettingsModel):
    _layout = "compact"
    ayon: str = SettingsField(title="AYON")
    type: str = SettingsField(
        title="Field type",
        disabled=True,
    )
    sg: str = SettingsField(title="SG")
    scope: list[str] = SettingsField(
        title="Scope",
        default_factory=list,
        enum_resolver=default_shotgrid_entities
    )


class ShotgridCompatibilitySettings(BaseSettingsModel):
    """ Settings to define relationships between ShotGrid and AYON.
    """
    shotgrid_enabled_entities: list[str] = SettingsField(
        title="ShotGrid Enabled Entities",
        default_factory=default_shotgrid_enabled_entities,
        enum_resolver=default_shotgrid_entities,
        description=(
            "The Entities that are enabled in ShotGrid, disable "
            "any that you do not use."
        ),
    )

    custom_attribs_map: list[AttributesMappingModel] = SettingsField(
        title="Folder Attributes Map",
        default_factory=get_default_folder_attributes,
        description=(
            "AYON attributes <> ShotGrid fields (without 'sg_' prefix!) "
            "mapping. Empty ones will be ignored. Scope is the list of "
            "ShotGrid entities that the mapping applies to. Disable any."
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
    """ShotGrid integration settings.

    Main setting for the AYON x ShotGrid integration, these need to be filled
    out in order to for the services to correctly operate.
    """

    shotgrid_server: str = SettingsField(
        default="",
        title="Shotgrid URL",
        description="The URL to the Shotgrid Server we want to interact with.",
        example="https://my-site.shotgrid.autodesk.com",
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
        title="ShotGrid Project Code field name",
        disabled=True,
        description=(
            "In order to create AYON projects, we need a Project Code, you "
            "can specify here which field in the ShotGrid Project "
            "entity represents it."
        ),
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
    anatomy_preset: str = SettingsField(
        default="_",
        title="Anatomy Preset",
        description=(
            "The anatomy preset to use for the "
            "ShotGrid synchronized projects."
        ),
        enum_resolver=anatomy_presets_enum
    )
    compatibility_settings: ShotgridCompatibilitySettings = SettingsField(
        default_factory=ShotgridCompatibilitySettings,
        title="ShotGrid <-> AYON compatibility Settings",
        description=(
            "All the settings that allow us to fine-grain the relation "
            "between ShotGrid and AYON entities."
        )
    )
    service_settings: ShotgridServiceSettings = SettingsField(
        default_factory=ShotgridServiceSettings,
        title="Service settings",
        scope=["studio"],
    )
