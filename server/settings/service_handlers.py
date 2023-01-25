from pydantic import Field

from ayon_server.settings import BaseSettingsModel

from .common import ROLES_TITLE


class PrepareProjectAction(BaseSettingsModel):
    enabled: bool = True
    role_list: list[str] = Field(default_factory=list, title=ROLES_TITLE)


class SyncFromShotgridAction(BaseSettingsModel):
    enabled: bool = True
    role_list: list[str] = Field(default_factory=list, title=ROLES_TITLE)


class ShotgridServiceHandlers(BaseSettingsModel):
    """Settings for event handlers running in shotgrid service."""

    prepare_project: PrepareProjectAction = Field(
        title="Prepare Project",
        default_factory=PrepareProjectAction,
    )
    sync_from_shotgrid: SyncFromShotgridAction = Field(
        title="Sync from shotgrid",
        default_factory=SyncFromShotgridAction,
    )


DEFAULT_SERVICE_HANDLERS_SETTINGS = {
    "prepare_project": {
        "enabled": True,
        "role_list": [
            "Administrator",
            "Project manager"
        ]
    },
    "sync_from_shotgrid": {
        "enabled": True,
        "role_list": [
            "Administrator",
            "Project manager"
        ]
    },
}

