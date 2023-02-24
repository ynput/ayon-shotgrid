import re
import collections
import time
import logging

from ayon_api import (
    get_project,
    create_project,
    EntityHub,
    slugify_name
)

from .lib.constants import SHOTGRID_PROJECT_ATTRIBUTES
from .lib.utils import (
    get_shotgrid_project_by_name,
    get_shotgrid_tasks,
    get_shotgrid_project_entities,
    get_shotgrid_project_hierarchy
)

from ftrack_common import (
    CUST_ATTR_KEY_SERVER_ID, # "ayon_id"
    CUST_ATTR_KEY_SERVER_PATH, # "ayon_path"
    CUST_ATTR_KEY_SYNC_FAIL, # "ayon_sync_failed"
    FTRACK_ID_ATTRIB, # "ftrackId"
    FTRACK_PATH_ATTRIB, #"ftrackPath" 
    REMOVED_ID_VALUE, # "removed"
    create_chunks, # Separate iterable into multiple chunks by size.
    get_custom_attributes_by_entity_id, # Query custom attribute values and store their value by entity and attr.
)


# Get all Ayon-dependant attributes form shotgrid
def _get_missing_custom_attrs(session):
    missing_attrs = []
    for ayon_attr, attr_dict in SHOTGRID_PROJECT_ATTRIBUTES.items():
        try:
            attribute_exists = shotgrid_session.schema_field_read(
                "Project",
                field_name=f"{sg_field_code}"
            )
        except Exception:
            # shotgun_api3.shotgun.Fault: API schema_field_read()
            logging.debug(
                f"Ayon Attribute {sg_field_code} does not exists."
            )
            missing_attrs.append(ayon_attr)

    return missing_attrs


class IdsMapping(object):
    def __init__(self):
        self._ftrack_to_server = {}
        self._server_to_ftrack = {}

    def set_ftrack_to_server(self, ftrack_id, server_id):
        self._ftrack_to_server[ftrack_id] = server_id
        self._server_to_ftrack[server_id] = ftrack_id

    def set_server_to_ftrack(self, server_id, ftrack_id):
        self.set_ftrack_to_server(ftrack_id, server_id)

    def get_server_mapping(self, ftrack_id):
        return self._ftrack_to_server.get(ftrack_id)

    def get_ftrack_mapping(self, server_id):
        return self._server_to_ftrack.get(server_id)


class SyncFromShotgrid:
    """Helper for sync project from ftrack."""

    def __init__(self, session, project_name, log=None):
        self._log = log
        self._sg_session = session
        self._project_name = project_name
        self._ids_mapping = IdsMapping()
        # Create entity hub which handle entity changes
        self._entity_hub = EntityHub(project_name)

        self._report_items = []

        # TODO add more and use them
        self._processed_server_ids = set()
        self._processed_shotgrid_ids = set()
        self._skipped_shotgrid_ids = set()
        self._duplicated_shotgrid_ids = {}
        # Immutable
        self._im_invalid_entity_ids = set()
        self._im_renamed_entity_ids = set()
        self._im_moved_entity_ids = set()
        self._im_removed_entity_ids = set()

    @property
    def project_name(self):
        return self._project_name

    @property
    def log(self):
        if self._log is None:
            self._log = logging.getLogger(self.__class__.__name__)
        return self._log

    @property
    def report_items(self):
        return self._report_items

    def sync_to_server(self, preset_name=None):
        t_start = time.perf_counter()
        project_name = self.project_name
        sg_session = self._sg_session

        self.log.info(f"Synchronization of project \"{project_name}\" started")

        # Check if there is custom attribute to store server id
        missing_attrs = _get_missing_custom_attrs()

        if missing_attrs:
            msg = (
                f"Shotgrid is missing attributes: {missing_attrs}"
                "Please run the 'Create attributes' event from the Addon Page."
            )
            self.log.warning(msg)
            raise ValueError(msg)

        # Query ftrack project
        sg_project = get_shotgrid_project_by_name(sg_session, project_name)
        # Make sure project exists on server
        # TODO: Create `get_or_create_project` in `ayon-python-api`
        ay_project = self.make_sure_project_exists(sg_project, preset_name)
        self._ids_mapping.set_shotgrid_to_server(
            sg_project["id"], ay_project["id"]
        )
        t_project_existence_1 = time.perf_counter()
        self.log.debug(
            f"Project existence check took {t_project_existence_1 - t_start}"
        )

        self.log.debug("Loading entities from Ayon server.")
        # Query entities from server (project, folders and tasks)
        self._entity_hub.query_entities_from_server()
        t_server_query_2 = time.perf_counter()
        self.log.debug((
            "Loading of entities from Ayon server"
            f" took {t_server_query_2 - t_project_existence_1}"
        ))

        self.log.info("Querying Tasks and Data Types from Shotgrid.")
        # Update types on project entity from ftrack
        self.update_project_types(sg_session, sg_project["id"])

        ft_object_type_name_by_id = {
            object_type["id"]: object_type["name"]
            for object_type in get_shotgrid_project_entities(sg_session, sg_project["id"])
        }
        ft_type_names_by_id = {
            task_type["id"]: task_type["name"]
            for task_type in get_shotgrid_tasks(sg_session, sg_project)
        }

        t_types_sync_3 = time.perf_counter()
        self.log.debug((
            "Update of types from ftrack"
            f" took {t_types_sync_3 - t_server_query_2}"
        ))

        self.log.info("Querying project hierarchy from Shotgrid.")
        # ft_entities = sg_session.query((
        #     "select id, name, parent_id, type_id, object_type_id"
        #     " from TypedContext where project_id is \"{}\""
        # ).format(sg_project["id"])).all()
        #ft_entities, ft_entities_by_id, ft_entities_by_parent_id
        sg_project_hierarchy, sg_entities_by_id, sg_entities_by_parent_id = project_hierarchy_encore(sg, sg_project)
        t_ft_entities_4 = time.perf_counter()

        self.log.debug((
            f"Query of ftrack entities took {t_ft_entities_4 - t_types_sync_3}"
        ))

        # ft_entities_by_id = {sg_project["id"]: sg_project}
        # ft_entities_by_parent_id = collections.defaultdict(list)
        # for entity in ft_entities:
        #     entity_id = entity["id"]
        #     parent_id = entity["parent_id"]
        #     ft_entities_by_id[entity_id] = entity
        #     ft_entities_by_parent_id[parent_id].append(entity)
        
        # ft_entity_ids = set(ft_entities_by_id.keys())
        sg_entities_id = set(sg_entities_by_id.keys())
        # cust_attr_value_by_entity_id = get_custom_attributes_by_entity_id(
        #     sg_session, ft_entity_ids, attr_confs, hier_attr_confs
        # )
        self.log.info("Checking changes of immutable entities")
        self.match_immutable_entities(
            sg_project,
            ft_entities_by_id,
            ft_entities_by_parent_id,
        )

        self.log.info("Matching ftrack to server hierarchy")
        # self.match_existing_entities(
        #     sg_project,
        #     ft_entities_by_parent_id,
        #     ft_object_type_name_by_id,
        #     ft_type_names_by_id,
        #     cust_attr_value_by_entity_id
        # )

        self.log.info("Updating attributes of entities")
        # self.update_attributes_from_ftrack(
        #     cust_attr_value_by_entity_id,
        #     ft_entities_by_id
        # )
        self._entity_hub.commit_changes()

        self.log.info("Updating server ids on ftrack entities")
        self.update_ftrack_attributes(
            ft_entities_by_id,
            cust_attr_value_by_entity_id,
            server_id_conf,
            server_path_conf,
            sync_failed_conf
        )
        self.create_report(ft_entities_by_id)
        t_end = time.perf_counter()
        self.log.info((
            f"Synchronization of project \"{project_name}\" finished"
            f" in {t_end-t_start}"
        ))

    def make_sure_project_exists(self, sg_project, preset_name=None):
        project_name = sg_project["name"]
        # Make sure project exists on server
        project = get_project(project_name)
        if not project:
            self.log.info(f"Creating project \"{project_name}\" on server")
            if not sg_project["code"]:
                project_code = project_name.replace(" ", "").lower()[:3]
            else:
                project_code = sg_project["code"]

            project = create_project(
                project_name,
                project_code,
                preset_name=preset_name
            )

        return project

    def update_project_types(self, object_types, task_types):
        project_entity = self._entity_hub.project_entity

        sg_tasks = [
            {"name": task["content"], "shortName": task["content"].lower()[:4]}
            for task in get_shotgrid_tasks()
        ]
        new_tasks = sg_tasks + project_entity.task_types
        new_tasks = list({
            task['name']: task
            for task in new_tasks
        }.values())

        sg_entities = [
            {"name": next(iter(entity.keys()))}
            for entity in get_shotgrid_project_entities()
        ]

        new_entities = sg_entities + project_entity.folder_types
        new_entities = list({
            entity['name']: entity
            for entity in new_entities
        }.values())

        project_entity.folder_types = new_entities
        project_entity.task_types = new_tasks

    def match_immutable_entities(
        self,
        sg_project,
        ft_entities_by_id,
        ft_entities_by_parent_id,
    ):
        self.log.debug("Validation of immutable entities started")

        # Collect all ftrack ids from immuable entities
        immutable_queue = collections.deque()
        for entity in self._entity_hub.project_entity.children:
            if entity.immutable_for_hierarchy:
                immutable_queue.append(entity)

        all_immutable_ftrack_ids = set()
        while immutable_queue:
            entity = immutable_queue.popleft()
            all_immutable_ftrack_ids.add(entity.attribs[FTRACK_ID_ATTRIB])
            for child in entity.children:
                immutable_queue.append(child)

        # Go through entities and find matching ftrack entity id
        hierarchy_queue = collections.deque()
        for entity in self._entity_hub.project_entity.children:
            if entity.immutable_for_hierarchy:
                hierarchy_queue.append((entity, sg_project["id"]))

        while hierarchy_queue:
            (entity, ft_parent_id) = hierarchy_queue.popleft()

            expected_ftrack_id = entity.attribs[FTRACK_ID_ATTRIB]
            ft_entity = ft_entities_by_id.get(expected_ftrack_id)
            if ft_entity is None:
                ft_children = []
                if ft_parent_id is not None:
                    ft_children = ft_entities_by_parent_id[ft_parent_id]

                is_folder = entity.entity_type == "folder"
                for ft_child in ft_children:
                    # Skip all entities that are already reserved for other
                    #   entities
                    if ft_child["id"] in all_immutable_ftrack_ids:
                        continue
                    name = slugify_name(ft_child["name"])
                    if name != entity.name:
                        continue
                    ft_is_folder = ft_child.entity_type != "Task"
                    if is_folder is ft_is_folder:
                        ft_entity = ft_child
                        break

                if ft_entity is None:
                    # Make sure 'expected_ftrack_id' is None
                    expected_ftrack_id = None
                    # Set ftrack id on entity to removed
                    entity.attribs[FTRACK_ID_ATTRIB] = REMOVED_ID_VALUE
                else:
                    # Change ftrack id of entity to matching ftrack entity
                    expected_ftrack_id = ft_entity["id"]
                    entity.attribs[FTRACK_ID_ATTRIB] = expected_ftrack_id
                    # Add the ftrack id to immutable ids
                    all_immutable_ftrack_ids.add(expected_ftrack_id)

            else:
                valid = True
                ft_name = slugify_name(ft_entity["name"])
                if ft_name != entity.name:
                    self._im_renamed_entity_ids.add(entity.id)
                    valid = False

                if ft_entity["parent_id"] != ft_parent_id:
                    self._im_moved_entity_ids.add(entity.id)
                    valid = False

                if not valid:
                    self._im_invalid_entity_ids.add(entity.id)

            if expected_ftrack_id:
                self._processed_ftrack_ids.add(expected_ftrack_id)
                self._ids_mapping.set_server_to_ftrack(
                    entity.id, expected_ftrack_id)

            self._processed_server_ids.add(entity.id)
            for child in entity.children:
                if child.immutable_for_hierarchy:
                    hierarchy_queue.append((child, expected_ftrack_id))

    def _create_new_entity(
        self,
        parent_entity,
        ft_entity,
        ft_object_type_name_by_id,
        ft_type_names_by_id,
        cust_attr_value_by_entity_id,
    ):
        ftrack_id = ft_entity["id"]
        custom_attributes = cust_attr_value_by_entity_id[ftrack_id]
        entity_id = custom_attributes.get(CUST_ATTR_KEY_SERVER_ID)

        label = ft_entity["name"]
        name = slugify_name(label)
        entity_type = ft_entity.entity_type
        if entity_type.lower() == "task":
            task_type_name = ft_type_names_by_id[ft_entity["type_id"]]
            new_entity = self._entity_hub.add_new_task(
                task_type_name,
                name=name,
                label=label,
                entity_id=entity_id,
                parent_id=parent_entity.id
            )

        else:
            object_type = ft_object_type_name_by_id[
                ft_entity["object_type_id"]]
            new_entity = self._entity_hub.add_new_folder(
                object_type,
                name=name,
                label=label,
                entity_id=entity_id,
                parent_id=parent_entity.id
            )
        self._ids_mapping.set_ftrack_to_server(ftrack_id, new_entity.id)

        return new_entity

    def match_existing_entities(
        self,
        sg_project,
        ft_entities_by_parent_id,
        ft_object_type_name_by_id,
        ft_type_names_by_id,
        cust_attr_value_by_entity_id,
    ):
        """Match exiting entities on both sides.

        Create new entities that are on ftrack and are not on server and remove
        those which are not on ftrack.

        Todos:
            Handle duplicates more clearly. Don't compare children only by name
                but also by type (right now task == folder).

        Args:
            sg_project (ftrack_api.Entity): Ftrack project entity.
            ft_entities_by_parent_id (dict[str, list[ftrack_api.Entity]]): Map
                of ftrack entities by their parent ids.
            ft_object_type_name_by_id (Dict[str, str]): Mapping of ftrack
                object type ids to their names.
            ft_type_names_by_id (Dict[str, str]): Mapping of ftrack task type
                ids to their names.
        """

        fill_queue = collections.deque()
        for ft_child in ft_entities_by_parent_id[sg_project["id"]]:
            fill_queue.append((self._entity_hub.project_entity, ft_child))

        def _add_children_to_queue(ft_entity_id):
            children = ft_entities_by_parent_id[ft_entity_id]
            if not children:
                return

            entity_id = self._ids_mapping.get_server_mapping(ft_entity_id)
            entity = None
            if entity_id:
                entity = self._entity_hub.get_entity_by_id(entity_id)

            for ft_child in children:
                fill_queue.append((entity, ft_child))

        while fill_queue:
            (parent_entity, ft_entity) = fill_queue.popleft()
            ft_entity_path = "/".join([
                item["name"]
                for item in ft_entity["link"]
            ])
            ft_entity_id = ft_entity["id"]
            # Go to next children if is already processed
            if ft_entity_id in self._processed_ftrack_ids:
                _add_children_to_queue(ft_entity_id)
                self.log.debug(
                    f"{ft_entity_path} - Ftrack id already processed")
                continue

            if parent_entity is None:
                self._skipped_ftrack_ids.add(ft_entity_id)
                _add_children_to_queue(ft_entity_id)
                self.log.debug(f"{ft_entity_path} - Skipped")
                continue

            label = ft_entity["name"]
            name = slugify_name(label)
            matching_name_entity = None
            for child in parent_entity.children:
                if child.name.lower() == name.lower():
                    matching_name_entity = child
                    break

            ft_is_folder = ft_entity.entity_type != "Task"
            if matching_name_entity is not None:
                # If entity was already processed we can skip ftrack entity
                # --- This is last condition that handle immutable entities ---
                #   After this condition can be server entities changed,
                #       removed or created.
                if matching_name_entity.id in self._processed_server_ids:
                    self._processed_ftrack_ids.add(ft_entity_id)
                    self._duplicated_ftrack_ids[ft_entity_id] = matching_name_entity
                    _add_children_to_queue(ft_entity_id)
                    self.log.debug(
                        f"{ft_entity_path} - Server id already processed")
                    continue

                is_folder = matching_name_entity.entity_type == "folder"
                # It is possible to remove previous server entity at this point
                #   as we're 100% sure it is not immutable at this point
                if ft_is_folder is not is_folder:
                    self.log.debug(
                        f"{ft_entity_path} - Deleted previous entity")
                    # Remove current entity if type does not match
                    matching_name_entity.parent_id = None
                    # Reset variable so new entity is created
                    matching_name_entity = None

            # No match was found, so we can create new server entity
            if matching_name_entity is None:
                self.log.debug(f"{ft_entity_path} - Creating new entity")
                entity = self._create_new_entity(
                    parent_entity,
                    ft_entity,
                    ft_object_type_name_by_id,
                    ft_type_names_by_id,
                    cust_attr_value_by_entity_id,
                )
                self._processed_server_ids.add(entity.id)
                self._processed_ftrack_ids.add(ft_entity_id)
                _add_children_to_queue(ft_entity_id)
                continue

            self.log.debug(f"{ft_entity_path} - Updating existing entity")
            matching_name_entity.name = name
            matching_name_entity.label = label
            matching_name_entity.active = True
            if matching_name_entity.entity_type == "task":
                task_type_id = ft_entity["type_id"]
                task_type_name = ft_type_names_by_id[task_type_id]
                if matching_name_entity.task_type != task_type_name:
                    matching_name_entity.task_type = task_type_name

            else:
                object_type_id = ft_entity["object_type_id"]
                object_type_name = ft_object_type_name_by_id[
                    object_type_id]
                if matching_name_entity.folder_type != object_type_name:
                    matching_name_entity.folder_type = object_type_name

            self._processed_server_ids.add(matching_name_entity.id)
            self._processed_ftrack_ids.add(ft_entity_id)
            self._ids_mapping.set_ftrack_to_server(
                ft_entity_id, matching_name_entity.id
            )
            _add_children_to_queue(ft_entity_id)

        deactivate_queue = collections.deque()
        for child in self._entity_hub.project_entity.children:
            deactivate_queue.append(child)

        while deactivate_queue:
            entity = deactivate_queue.popleft()
            if entity.id not in self._processed_server_ids:
                entity.active = False

            for child in entity.children:
                deactivate_queue.append(child)

    def update_attributes_from_ftrack(
        self, cust_attr_value_by_entity_id, ft_entities_by_id
    ):
        hierarchy_queue = collections.deque()
        hierarchy_queue.append(self._entity_hub.project_entity)
        while hierarchy_queue:
            entity = hierarchy_queue.popleft()
            # Add children to queue
            for child_entity in entity.children:
                hierarchy_queue.append(child_entity)

            ftrack_id = self._ids_mapping.get_ftrack_mapping(entity.id)
            if ftrack_id is None:
                continue

            ft_entity = ft_entities_by_id[ftrack_id]
            path = "/".join([
                item["name"]
                for item in ft_entity["link"]
                if item["type"] != "Project"
            ])
            entity.attribs[FTRACK_ID_ATTRIB] = ftrack_id
            entity.attribs[FTRACK_PATH_ATTRIB] = path
            # Ftrack id can not be available if ftrack entity was recreated
            #   during immutable entity processing
            attribute_values = cust_attr_value_by_entity_id[ftrack_id]
            is_project = entity.entity_type == "project"

            # TODO handle "data" to sync custom attributes not available
            #   in 'attribs'
            for key, value in attribute_values.items():
                # QUESTION Should we skip "unsetting" of project attributes?
                #   - very dangerous for OpenPype and maybe for project should
                #       be taken default value of attribute (if there is any)
                if is_project and value is None:
                    continue

                if key in entity.attribs:
                    entity.attribs[key] = value

    def _create_ft_operation(
        self, conf_id, entity_id, is_new, new_value, old_value=None
    ):
        entity_key = collections.OrderedDict((
            ("configuration_id", conf_id),
            ("entity_id", entity_id)
        ))
        if is_new:
            return ftrack_api.operation.CreateEntityOperation(
                "CustomAttributeValue",
                entity_key,
                {"value": new_value}
            )

        return ftrack_api.operation.UpdateEntityOperation(
            "CustomAttributeValue",
            entity_key,
            "value",
            old_value,
            new_value
        )

    def update_ftrack_attributes(
        self,
        ft_entities_by_id,
        cust_attr_value_by_entity_id,
        server_id_conf,
        server_path_conf,
        sync_failed_conf
    ):
        operations = []
        for ftrack_id, ft_entity in ft_entities_by_id.items():
            if ft_entity.entity_type == "Project":
                continue

            server_id = self._ids_mapping.get_server_mapping(ftrack_id)
            entity = None
            if server_id:
                entity = self._entity_hub.get_entity_by_id(server_id)

            entity_id = ""
            if entity is not None:
                entity_id = entity.id

            custom_attributes = cust_attr_value_by_entity_id[ftrack_id]

            oring_sync_failed = custom_attributes.get(CUST_ATTR_KEY_SYNC_FAIL)
            orig_id = custom_attributes.get(CUST_ATTR_KEY_SERVER_ID)
            orig_path = custom_attributes.get(CUST_ATTR_KEY_SERVER_PATH)
            sync_failed = False
            if entity is None or entity.id in self._im_invalid_entity_ids:
                sync_failed = True

            if sync_failed != oring_sync_failed:
                operations.append(
                    self._create_ft_operation(
                        sync_failed_conf["id"],
                        ftrack_id,
                        CUST_ATTR_KEY_SYNC_FAIL not in custom_attributes,
                        sync_failed,
                        oring_sync_failed
                    )
                )

            if orig_id != entity_id:
                operations.append(
                    self._create_ft_operation(
                        server_id_conf["id"],
                        ftrack_id,
                        CUST_ATTR_KEY_SERVER_ID not in custom_attributes,
                        entity_id,
                        orig_id
                    )
                )

            if ft_entity.entity_type == "Task" or sync_failed:
                continue

            path = entity.path
            if path != orig_path:
                operations.append(
                    self._create_ft_operation(
                        server_path_conf["id"],
                        ftrack_id,
                        CUST_ATTR_KEY_SERVER_PATH not in custom_attributes,
                        path,
                        orig_path
                    )
                )

        if not operations:
            return

        for chunk in create_chunks(operations, 500):
            for operation in chunk:
                self._sg_session.recorded_operations.push(operation)
            self._sg_session.commit()

    def create_report(self, ft_entities_by_id):
        report_items = []

        # --- Immutable entities ---
        # Removed entities - they don't have ftrack euqivalent anymore
        deleted_paths = []
        for entity_id in self._im_removed_entity_ids:
            entity = self._entity_hub.get_entity_by_id(entity_id)
            path = entity.attribs[FTRACK_PATH_ATTRIB]
            if not path:
                path = entity.path
            deleted_paths.append(path)

        deleted_paths.sort()
        if deleted_paths:
            report_items.append({
                "type": "label",
                "value": "## Not found entities"
            })
            for path in deleted_paths:
                self.log.info((
                    f"Skipped sync of immutable entity {path} (was removed)"
                ))
                report_items.append({"type": "label", "value": f"- {path}"})

        # Changed position or name
        renamed_mapping = {}
        changed_hierarchy = (
            self._im_renamed_entity_ids | self._im_moved_entity_ids
        )
        for entity_id in changed_hierarchy:
            entity = self._entity_hub.get_entity_by_id(entity_id)
            ftrack_id = entity.attribs[FTRACK_ID_ATTRIB]
            ft_entity = ft_entities_by_id.get(ftrack_id)
            if ft_entity is None:
                continue
            path = "/".join([
                item["name"]
                for item in ft_entity["link"]
                if item["type"] != "Project"
            ])
            expected_path = entity.attribs[FTRACK_PATH_ATTRIB]
            if not expected_path:
                expected_path = entity.path
            renamed_mapping[path] = expected_path

        renamed_paths = []
        for path in sorted(renamed_mapping.keys()):
            renamed_paths.append((path, renamed_mapping[path]))

        if renamed_paths:
            if report_items:
                report_items.append({"type": "label", "value": "---"})
            report_items.append({
                "type": "label",
                "value": "## Renamed/Moved entities"
            })
            report_items.append({
                "type": "label",
                "value": (
                    "Entities were renamed or moved to different location"
                    " but it is not allowed to propagate the change."
                )
            })
            for (path, expected_path) in renamed_paths:
                self.log.info((
                    "Skipped sync of immutable"
                    f" entity {path} -> {expected_path}"
                ))
                report_items.append({
                    "type": "label",
                    "value": f"- {path} -> {expected_path}"
                })

        # --- Other possible issues ---
        synced_path_mapping = collections.defaultdict(list)
        for ftrack_id, entity in self._duplicated_ftrack_ids.items():
            synced_path = entity.attribs[FTRACK_PATH_ATTRIB]
            ft_entity = ft_entities_by_id.get(ftrack_id)
            if ft_entity is not None:
                path = "/".join([
                    item["name"]
                    for item in ft_entity["link"]
                    if item["type"] != "Project"
                ])
                synced_path_mapping[synced_path].append(path)

        if synced_path_mapping:
            if report_items:
                report_items.append({"type": "label", "value": "---"})

            report_items.append({
                "type": "label",
                "value": "## Duplicated names"
            })
            for synced_path in sorted(synced_path_mapping.keys()):
                paths = synced_path_mapping[synced_path]
                self.log.info((
                    "Skipped sync because duplicated names."
                    "\nSource entity: {}\n{}"
                ).format(
                    synced_path,
                    "\n".join([f"- {path}" for path in paths])
                ))
                report_items.append({
                    "type": "label",
                    "value": f"### {synced_path}"
                })
                for path in paths:
                    report_items.append({
                        "type": "label",
                        "value": f"- {path}"
                    })

        self._report_items = report_items
