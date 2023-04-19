"""Class that will create, update or remove an Ayon entity based on the `meta`
dictionary of a Shotgrid Event Payload, for example:
"meta": {
    "id": 1274,
    "type": "entity_retirement",
    "entity_id": 1274,
    "class_name": "Shot",
    "entity_type": "Shot",
    "display_name": "bunny_099_012",
    "retirement_date": "2023-03-31 15:26:16 UTC"
}

At most time it fetches the SG entiy as an Ayon dict:
{
    "label": label,
    "name": name,
    SHOTGRID_ID_ATTRIB: shotgrid id,
    CUST_FIELD_CODE_ID: ayon id stored in Shotgrid,
    CUST_FIELD_CODE_SYNC: sync status stored in shotgrid,
    "type": the entity type,
}

"""

from .utils import (
    get_sg_entity_as_ay_dict,
    get_sg_entity_parent_field,
    get_sg_project_by_id,
)
from .constants import (
    CUST_FIELD_CODE_ID,  # Shotgrid Field for the Ayon ID.
    CUST_FIELD_CODE_AUTO_SYNC,  # Shotgrid Field for the Auto Sync toggle.
    SHOTGRID_ID_ATTRIB,  # Ayon Entity Attribute.
    SHOTGRID_TYPE_ATTRIB,  # Ayon Entity Attribute.
    SHOTGRID_REMOVED_VALUE
)

from ayon_api import get_project
from ayon_api.entity_hub import EntityHub
from nxtools import logging


ALLOWED_SG_FIELDS = [
    "code",
    "name",
]


class UpdateFromShotgrid:
    def __init__(self, sg_session, sg_event_payload, log=None):
        self._sg_session = sg_session
        self.log = log if log else logging
        self._action = None

        if not sg_event_payload:
            raise ValueError("The Event Payload is empty.")

        self._sg_project = get_sg_project_by_id(
            self._sg_session,
            sg_event_payload["project"]["id"],
            extra_fields=[CUST_FIELD_CODE_AUTO_SYNC]
        )

        self._sg_event = sg_event_payload["meta"]

        if not self._sg_project.get(CUST_FIELD_CODE_AUTO_SYNC):
            raise ValueError(
                f"Project {self._sg_project['name']} has AutoSync disabled."
            )

        if not get_project(self._sg_project.get(CUST_FIELD_CODE_ID, "")):
            raise ValueError(
                f"Project {self._sg_project[CUST_FIELD_CODE_ID]} not in Ayon."
            )

        match self._sg_event["type"]:
            case "new_entity" | "entity_revival":
                self._action = self.create_entity
            case "attribute_change":
                if self._sg_event["attribute_name"] not in ALLOWED_SG_FIELDS:
                    self.log.warning("Can't handle this attribute.")
                    return
                self._action = self.update_entity
            case "entity_retirement":
                self._action = self.remove_entity
            case _:
                msg = f"Unable to process event {self._sg_event['type']}."
                self.log.error(msg)
                raise ValueError(msg)

        self._entity_hub = EntityHub(
            self._sg_project.get(CUST_FIELD_CODE_ID, "")
        )

        self.log.debug(self._sg_event)

    def process_event(self):
        """Trigger the defined action."""

        if not self._action:
            self.log.error(f"No action to perform for {self._sg_event}")
            return

        self._entity_hub.query_entities_from_server()
        return self._action()

    def create_entity(self):
        """Try to create an entity in Ayon.
        """
        sg_parent_field = get_sg_entity_parent_field(
            self._sg_session,
            self._sg_project,
            self._sg_event["entity_type"],
        )

        sg_entity_dict = get_sg_entity_as_ay_dict(
            self._sg_session,
            self._sg_event["entity_type"],
            self._sg_event["entity_id"],
            extra_fields=[sg_parent_field],
        )
        self.log.debug(f"SG Entity as Ay dict: {sg_entity_dict}")

        if sg_entity_dict.get(CUST_FIELD_CODE_ID):
            # Revived entity, check if it still in the Server
            ay_entity = self._entity_hub.get_entity_by_id(
                sg_entity_dict.get(CUST_FIELD_CODE_ID)
            )

            if ay_entity:
                # Ensure Ay Entity has the correct Shotgird ID
                ay_shotgrid_id = sg_entity_dict.get(SHOTGRID_ID_ATTRIB, "")
                if ay_entity.attribs.get_attribute(SHOTGRID_ID_ATTRIB).value != str(ay_shotgrid_id):
                    ay_entity.attribs.set(
                        SHOTGRID_ID_ATTRIB,
                        ay_shotgrid_id
                    )
                    ay_entity.attribs.set(
                        SHOTGRID_TYPE_ATTRIB,
                        sg_entity_dict["type"]
                    )

                return ay_entity

        # Find parent entity ID
        sg_parent_entity_dict = get_sg_entity_as_ay_dict(
            self._sg_session,
            sg_entity_dict[sg_parent_field]["type"],
            sg_entity_dict[sg_parent_field]["id"],
        )

        ay_parent_entity = self._entity_hub.get_entity_by_id(
            sg_parent_entity_dict.get(CUST_FIELD_CODE_ID)
        )

        if not ay_parent_entity:
            # This really should be an edge  ase, since any parent event would
            # happen before this... but hey
            raise ValueError("Parent does not exist in Ayon.")

        if sg_entity_dict["type"].lower() == "task":
            ay_entity = self._entity_hub.add_new_task(
                sg_entity_dict["label"],
                name=sg_entity_dict["name"],
                label=sg_entity_dict["label"],
                entity_id=sg_entity_dict[CUST_FIELD_CODE_ID],
                parent_id=ay_parent_entity.id
            )
        else:
            ay_entity = self._entity_hub.add_new_folder(
                sg_entity_dict["type"],
                name=sg_entity_dict["name"],
                label=sg_entity_dict["label"],
                entity_id=sg_entity_dict[CUST_FIELD_CODE_ID],
                parent_id=ay_parent_entity.id
            )

        ay_entity.attribs.set(
            SHOTGRID_ID_ATTRIB,
            sg_entity_dict.get(SHOTGRID_ID_ATTRIB, "")
        )
        ay_entity.attribs.set(
            SHOTGRID_TYPE_ATTRIB,
            sg_entity_dict.get(SHOTGRID_TYPE_ATTRIB, "")
        )

        try:
            self._entity_hub.commit_changes()

            self._sg_session.update(
                sg_entity_dict["type"],
                sg_entity_dict[SHOTGRID_ID_ATTRIB],
                {
                    CUST_FIELD_CODE_ID: ay_entity.id
                }
            )
        except Exception as e:
            self.log.error(e)
            pass

        return ay_entity

    def update_entity(self):
        """Try to update an entity in Ayon.
        """
        sg_entity_dict = get_sg_entity_as_ay_dict(
            self._sg_session,
            self._sg_event["entity_type"],
            self._sg_event["entity_id"],
        )

        if not sg_entity_dict.get(CUST_FIELD_CODE_ID):
            self.log.warning("Shotgrid Missing Ayon ID")

        ay_entity = self._entity_hub.get_entity_by_id(
            sg_entity_dict.get(CUST_FIELD_CODE_ID)
        )

        if not ay_entity:
            self.log.error("Unable to update an non existant entity.")
            raise ValueError("Unable to update an non existant entity.")

        if int(ay_entity.attribs.get_attribute(SHOTGRID_ID_ATTRIB).value) != int(sg_entity_dict.get(SHOTGRID_ID_ATTRIB)):
            self.log.error("Missmatching Shotgrid IDs, aborting...")
            raise ValueError("Missmatching Shotgrid IDs, aborting...")

        if self._sg_event["attribute_name"] in ["code", "name"]:
            if ay_entity.name != sg_entity_dict["name"]:
                ay_entity.name = sg_entity_dict["name"]

            if ay_entity.label != sg_entity_dict["label"]:
                ay_entity.label = sg_entity_dict["label"]

        self._entity_hub.commit_changes()

        if sg_entity_dict.get(CUST_FIELD_CODE_ID) != ay_entity.id:
            self._sg_session.update(
                sg_entity_dict["type"],
                sg_entity_dict[SHOTGRID_ID_ATTRIB],
                {
                    CUST_FIELD_CODE_ID: ay_entity.id
                }
            )

        return ay_entity

    def remove_entity(self):
        """Try to remove an entity in Ayon.
        """
        sg_entity_dict = get_sg_entity_as_ay_dict(
            self._sg_session,
            self._sg_event["entity_type"],
            self._sg_event["entity_id"],
            retired_only=True
        )

        self.log.debug(f"SG Entity as Ay dict: {sg_entity_dict}")
        if not sg_entity_dict:
            self.log.warning(f"Entity {self._sg_event['entity_type']} <{self._sg_event['entity_id']}> no longer exists in SG.")
            raise ValueError(f"Entity {self._sg_event['entity_type']} <{self._sg_event['entity_id']}> no longer exists in SG.")

        if not sg_entity_dict.get(CUST_FIELD_CODE_ID):
            self.log.warning("Shotgrid Missing Ayon ID")
            raise ValueError("Shotgrid Missing Ayon ID")

        ay_entity = self._entity_hub.get_entity_by_id(
            sg_entity_dict.get(CUST_FIELD_CODE_ID)
        )

        if not ay_entity:
            self.log.error("Unable to update an non existant entity.")
            raise ValueError("Unable to update an non existant entity.")

        if sg_entity_dict.get(CUST_FIELD_CODE_ID) != ay_entity.id:
            self.log.error("Missmatching Shotgrid IDs, aborting...")
            raise ValueError("Missmatching Shotgrid IDs, aborting...")

        if not ay_entity.immutable_for_hierarchy:
            self._entity_hub.delete_entity(ay_entity)
        else:
            self.log.info("Entity is immutable.")
            ay_entity.attribs.set(SHOTGRID_ID_ATTRIB, SHOTGRID_REMOVED_VALUE)

        self._entity_hub.commit_changes()

