# Custom Fields Created in Shotgrid
CUST_FIELD_CODE_ID = "sg_ayon_id"
CUST_FIELD_CODE_SYNC = "sg_ayon_sync_status"
CUST_FIELD_CODE_AUTO_SYNC = "sg_ayon_auto_sync"
CUST_FIELD_CODE_CODE = "sg_ayon_project_code"
CUST_FIELD_CODE_URL = "sg_ayon_server_url"
SHOTGRID_REMOVED_VALUE = "removed"

SHOTGRID_ID_ATTRIB = "shotgridId"
SHOTGRID_PATH_ATTRIB = "shotgridPath"
SHOTGRID_TYPE_ATTRIB = "shotgridType"


REMOVED_ID_VALUE = "removed"

SG_PROJECT_ATTRS = {
    "ayon_id": {
        "name": "Ayon ID",
        "type": "text",
        "sg_field": CUST_FIELD_CODE_ID,
    },
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
    "Scene": "folder",
    "Shot": "folder",
    "Asset": "folder",
    "Task": "task",
    "Version": "version",
    "Comment": "note",
    "Playlist": "entity_list",
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
    "sg_scene",
    "shots",
    "sg_asset_type",
    "content",
    "entity",
    "step",
    "step.Step.code",
    "task_assignees",
    CUST_FIELD_CODE_ID,
    CUST_FIELD_CODE_SYNC,
]

SG_RESTRICTED_ATTR_FIELDS = [
    "code",
    "name"
]

SG_EVENT_TYPES = [
    "Shotgun_{0}_New",  # a new entity was created.
    "Shotgun_{0}_Change",  # an entity was modified.
    "Shotgun_{0}_Retirement",  # an entity was deleted.
    "Shotgun_{0}_Revival",  # an entity was revived.
]

SG_EVENT_QUERY_FIELDS = [
    "id",
    "event_type",
    "attribute_name",
    "meta",
    "entity",
    "user",
    "project",
    "session_uuid",
    "created_at",
]


class FOLDER_REPARENTING_TYPE:
    ROOT_RELOCATE = "root_relocate"
    TYPE_GROUPING = "type_grouping"


SHOTGRID_COMMENTS_TOPIC = "shotgrid.sync.comments"
COMMENTS_SYNC_INTERVAL = 15  # secs
COMMENTS_SYNC_TIMEOUT = 60 * 2  # secs
COMMENTS_PARENTING_ORDER = (
    "version",
    "shot",
    "asset",
    "sequence",
    "episode",
    "project"
)
