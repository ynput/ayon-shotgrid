# Custom Fields Created in Shotgrid
CUST_FIELD_CODE_ID = "sg_ayon_id"
CUST_FIELD_CODE_SYNC = "sg_ayon_sync_status"
CUST_FIELD_CODE_AUTO_SYNC = "sg_ayon_auto_sync"
CUST_FIELD_CODE_NAME = "sg_ayon_project_name"
CUST_FIELD_CODE_CODE = "sg_ayon_project_code"
CUST_FIELD_CODE_URL = "sg_ayon_server_url"
SHOTGRID_REMOVED_VALUE = "removed"

SHOTGRID_ID_ATTRIB = "shotgridId"
SHOTGRID_PATH_ATTRIB = "shotgridPath"


REMOVED_ID_VALUE = "removed"

SG_PROJECT_ATTRS = {
    "ayon_project_code": {
        "name": "Ayon Project Code",
        "type": "text",
        "sg_field": CUST_FIELD_CODE_CODE
    },
    "ayon_auto_sync": {
        "name": "Ayon Auto Sync",
        "type": "checkbox",
        "sg_field": CUST_FIELD_CODE_AUTO_SYNC,
    },
    "ayon_server_url": {
        "name": "Ayon Server URL",
        "type": "text",
        "sg_field": CUST_FIELD_CODE_URL,
    }
}

AYON_SHOTGRID_ENTITY_TYPE_MAP = {
    "Project": "project",
    "Episode": "folder",
    "Sequence": "folder",
    "Shot": "folder",
    "Asset": "folder",
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

SG_COMMON_ENTITY_FIELDS = [
    "code",
    "name",
    "sg_status",
    "sg_status_list",
    "tags",
    "project",
    "episode",
    "sg_sequence",
    "shots",
    "sg_asset_type",
    "content",
    "entity",
    CUST_FIELD_CODE_ID,
    CUST_FIELD_CODE_SYNC,
]
