SHOTGRID_PROJECT_ATTRIBUTES = {
    "ayon_project_name": "string",
    "ayon_auto_sync": "boolean",
    "ayon_server_url": "string",
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
