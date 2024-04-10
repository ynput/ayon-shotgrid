from ayon_server.entities.core.attrib import attribute_library
from ayon_server.settings import BaseSettingsModel, SettingsField
from ayon_server.settings.enum import secrets_enum, anatomy_presets_enum


def default_shotgrid_entities():
    """The entity types enabled in ShotGrid.

    Return a list to be consumed by the `enum_resolver` in
    `ShotgridCompatibilitySettings.shotgrid_enabled_entities`.
    """
    return [
        "Project",
        "Episode",
        "Sequence",
        "Shot",
        "Asset",
        "Task",
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
            "type": [attr_dict["type"]],
            "scope": default_shotgrid_entities()
        }

        if attr_map not in attributes:
            attributes.append(attr_map)

    return attributes


class ShotgridServiceSettings(BaseSettingsModel):
    """Specific settings for services

    ShotGrid Services: Processor, Leecher and Transmitter.

   The different services process events from either ShotGrid or AYON,
   this field allows to control how long to wait between each event
   is processed.
    """
    polling_frequency: int = SettingsField(
        default=10,
        title="How often (in seconds) to process ShotGrid related events.",
        validate_default=False,
    )


class AttributesMappingModel(BaseSettingsModel):
    _layout = "compact"
    ayon: str = SettingsField(title="AYON")
    sg: str = SettingsField(title="SG")
    # TODO: how do you make this a single selectable entry
    type: list[str] = SettingsField(
        title="Type",
        default_factory=list,
        enum_resolver=lambda: [
            "string",
            "integer",
            "float",
            "list_of_strings",
            "boolean",
            "datetime",
        ]
    )
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
        default_factory=default_shotgrid_entities,
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
          "mapping. Empty ones will be ignored."
        ),
    )


class ShotgridSettings(BaseSettingsModel):
    """ShotGrid integration settings.

    Main setting for the AYON x ShotGrid integration, these need to be filled
    out in order to for the services to correctly operate.
    """

    shotgrid_server: str = SettingsField(
        default="",
        title="ShotGrid URL",
        description="The URL to the ShotGrid Server we want to interact with.",
        example="https://my-site.shotgrid.autodesk.com"
    )
    shotgrid_api_secret: str = SettingsField(
        default="",
        enum_resolver=secrets_enum,
        title="ShotGrid API Secret",
        description=(
            "An AYON Secret where the key is the `script_name` and the value "
            "is the `api_key` from ShotGrid. See more at: "
            "https://developer.shotgridsoftware.com/python-api/authentication"
            ".html#setting-up-shotgrid"
        )
    )
    shotgrid_project_code_field: str = SettingsField(
        default="code",
        title="ShotGrid Project Code field name",
        description=(
            "In order to create AYON projects, we need a Project Code, you "
            "can specify here which field in the ShotGrid Project "
            "entity represents it."
        ),
        example="sg_code"
    )
    enable_shotgrid_local_storage: bool = SettingsField(
        default=True,
        title="Enable ShotGrid Local Storage.",
        description=(
            "Whether to try make use of local storage defined in ShotGrid "
            "('Site Preferences -> File Management -> Local Storage') or not."
        )
    )
    shotgrid_local_storage_key: str = SettingsField(
        default="primary",
        title="ShotGrid Local Storage entry name",
        description=(
            "Name of the 'code' to select which one of the multiple possible "
            "local storages entries to use."
        ),
        example="ayon_storage"
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
    )
