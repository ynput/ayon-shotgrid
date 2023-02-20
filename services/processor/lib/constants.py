SHOTGRID_PROJECT_ATTRIBUTES = {
    "ayon_project_name": {
        "name": "Ayon Project Name",
        "type": "text",
        "sg_field": "sg_ayon_project_name",
    },
    "ayon_project_code": {
        "name": "Ayon Project Code",
        "type": "text",
        "sg_field": "sg_ayon_project_code"
    },
    "ayon_auto_sync": {
        "name": "Ayon Auto Sync",
        "type": "checkbox",
        "sg_field": "sg_ayon_auto_sync",
    },
    "ayon_server_url": {
        "name": "Ayon Server URL",
        "type": "text",
        "sg_field": "sg_ayon_server_url",
    },
    "ayon_linux_root_path": {
        "name": "Ayon Linux Root Path",
        "type": "text",
        "sg_field": "sg_ayon_linux_root_path",
    },
    "ayon_macos_root_path": {
        "name": "Ayon MacOS Root Path",
        "type": "text",
        "sg_field": "sg_ayon_macos_root_path",
    },
    "ayon_windows_url": {
        "name": "Ayon Windows Root Path",
        "type": "text",
        "sg_field": "sg_ayon_windows_url",
    },
}

AYON_SHOTGRID_ENTITY_MAP = {
    "Project": "project",
    "Episode": "folder",
    "Sequence": "folder",
    "Shot": "folder",
    "Asset": "asset",
    "Version": "version",
    "Task": "task",
}


AYON_SHOTGRID_ATTRIBUTES_MAP = {
    "string": {
        "name": "text",
        "properties": [
            "name",
            "visible",
            "description",
            "summary_default",
            "custom_metadata"
        ],
    },
    "integer": {
        "name": "number",
        "properties": [
            "name",
            "visible",
            "description",
            "summary_default",
            "custom_metadata"
        ],
    },
    "float": {
        "name": "float",
        "properties": [
            "name",
            "visible",
            "description",
            "summary_default",
            "custom_metadata"
        ],
    },
    "boolean": {
        "name": "checkbox",
        "properties": [
            "name",
            "visible",
            "description",
            "summary_default",
            "default_value",
            "custom_metadata"
        ]
    },
    "datetime": {
        "name": "date_time",
        "properties": [
            "name",
            "visible",
            "description",
            "summary_default",
            "custom_metadata"
        ],
    },
    "list": {
        "name": "list",
        "properties": [
            "name",
            "visible",
            "description",
            "summary_default",
            "valid_values",
            "default_value",
            "custom_metadata"
        ],
    }
}
