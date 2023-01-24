"""
A Shotgird Webhooks listener addon for Ayon.

This service will continually run and query (and track) the EventLogEntry table from Shotgrid
and process any event that happens.

Example Shotgrid Event:
{'attribute_name': 'sg_status_list',
 'created_at': datetime.datetime(2023, 1, 23, 12, 1, 36, tzinfo=<shotgun_api3.lib.sgtimezone.LocalTimezone object at 0x7f68561146d0>),
 'entity': {'id': 23, 'name': 'bunny_010', 'type': 'Sequence'},
 'event_type': 'Shotgun_Sequence_Change',
 'id': 481455,
 'meta': {'attribute_name': 'sg_status_list',
          'entity_id': 23,
          'entity_type': 'Sequence',
          'field_data_type': 'status_list',
          'new_value': 'wtg',
          'old_value': 'ip',
          'type': 'attribute_change'},
 'project': {'id': 70, 'name': 'Demo: Animation', 'type': 'Project'},
 'session_uuid': '479b350c-9b15-11ed-9ead-0242ac110005',
 'type': 'EventLogEntry',
 'user': {'id': 88, 'name': 'Ayon Ynput', 'type': 'HumanUser'}}


"""
import sys
import time
import signal
from typing import Any, Callable, Union

import ayon_api
import ayclient
from nxtools import logging
import shotgun_api3


# Probably could allow thise to be configured via the Addon settings
# And do a query where we alread filter these out.
# Clearly not working, since these are ftrack specific ones.
IGNORE_TOPICS = {
    "ftrack.meta.connected",
    "ftrack.meta.disconnected",
}


# These should be defined on the Addon Frontend, see `main`
SHOTGUN_HOST = "https://ynput.shotgrid.autodesk.com"
SHOTGUN_SCRIPT_NAME = "ayon_leecher"
SHOTGUN_API_KEY = "super-secret-key"


def create_event_description(payload: dict[str, Any]):
    """ Helper method to generate event desciptions.

    """
    uname = payload.get("data", {}).get("user", {}).get("name")

    if not uname:
        return f"Leeched {payload['data']['operation']}"
    return f"Leeched {payload['data']['operation']} by {uname}"


def send_event_to_ayon(payload: dict[str, Any]):
    """ Send the Shotgrid event as an Ayon event.

    Args:
        payload (dict): The Event data.

    Returns:
        int: The Shotgrid Event ID.
    """
    if payload['operation'] in IGNORE_TOPICS:
        return

    ayon_api.events.dispatch_event(
        "shotgrid.leech",
        sender=ayclient.config.service_name,
        hash=payload["id"],
        description=create_event_description(payload),
        payload=payload,
    )
    logging.info("Stored event", payload['operation'])

    return payload["id"]


def listen_loop(session, callback, last_event_id=None):
    """ Main loop querying the Shotgrid database for new events

    Since Shotgrid does not have an event hub per se, we need to query
    the "EventLogEntry table and send these as Ayon events for processing.

    Args:
        session (shotgun_api3.Shotgun): Shotgrid Session object.
        callback (function): The function to run for each event.
        last_event_id (int|Optional): If specified, the query will return all
            Events since the provided ID.
    """

    fields = [
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
    order = [{"column": "id", "direction": "asc"}]

    if not last_event_id:
        last_event = session.find_one(
            "EventLogEntry",
            filters=[],
            fields=["id"],
            order=[{"column": "id", "direction": "desc"}]
        )

        if last_event:
            logging.info(f"Last Event ID is {last_event['id']}")
            last_event_id = last_event["id"]

    while True:
        logging.debug(f"The last processed event was {last_event_id}")
        filters = None
        filters = [["id", "greater_than", last_event_id]]

        try:
            events = session.find(
                "EventLogEntry",
                filters,
                fields,
                order,
                limit=50,  # settings.number_of_batch_events
            )
            if events:
                logging.info(f"Query returned {len(events)} events.")

                for event in events:
                    if not event:
                        continue

                    last_event_id = callback(event)

                logging.debug(f"Last event ID is... {last_event_id}")

        except Exception as err:
            logging.error(err)

        time.sleep(10)  # settings.pull_frequency
        logging.info("Waiting...")


def main(func: Union[Callable, None] = None):
    logging.info("Starting listener")

    if func is None:
        func = send_event_to_ayon

    addon_settings = ayclient.addon_settings()

    sg = shotgun_api3.Shotgun(
        SHOTGUN_HOST,  # addon_settings.shotgrid_host
        script_name=SHOTGUN_SCRIPT_NAME,  # addon_settings.script_name
        api_key=SHOTGUN_API_KEY)  # addon_settings.shotgrid_api_key

    try:
        sg.connect()
    except Exception as e:
        logging.error("Unable to connect to Shotgrid Instance:")
        logging.error(e)

    # Register interrupt signal
    def signal_handler(sig, frame):
        logging.warning("Process stop requested. Terminating process.")
        sg.close()
        logging.warning("Termination finished.")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logging.info("Main loop starting")
    sys.exit(listen_loop(sg, func))
    logging.info("Process stopped")

