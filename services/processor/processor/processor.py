"""
A Shotgrid Events listener processor for Ayon.

This service will continually run and query the Ayon Events Server in orther to
entroll the events of topic `shotgrid.leech` to perform processing of Shotgrid
related events.
"""
import os
import sys
from pprint import pformat
import time
import types
import socket
import importlib.machinery
import traceback

import ayon_api
import shotgun_api3

from utils import get_logger, get_event_hash

from constants import MissingParentError

class ShotgridProcessor:
    _sg: shotgun_api3.Shotgun = None
    _RETRIGGERED_TOPIC = "shotgrid.event.retriggered"
    log = get_logger(__file__)

    def __init__(self):
        """A class to process AYON events of `shotgrid.event` topic.

        These events contain an "action" key in the payload, which is
        used to match to any handler that has REGISTER_EVENT_TYPE attribute.

        For example, the `handlers/project_sync.py` will be triggered whenever
        an event has the action "create-project", since it has the following
        constant declared `REGISTER_EVENT_TYPE = ["create-project"]`.

        New handlers can be added to the `handlers` directory and as long as they
        have `REGISTER_EVENT_TYPE` declared, if an event with said action is pending,
        it will be triggered, this directory is traversed upon initialization.

        In order for this service to work, the settings for the Addon have to be
        populated in 'AYON > Studio Settings > Shotgrid'.
        """
        self.log.info("Initializing the Shotgrid Processor.")

        self.handlers_map = None

        try:
            ayon_api.init_service()
            self.settings = ayon_api.get_service_addon_settings()
            service_settings = self.settings["service_settings"]

            self.sg_url = self.settings["shotgrid_server"]
            self.sg_project_code_field = self.settings[
                "shotgrid_project_code_field"]

            # get server op related ShotGrid script api properties
            shotgrid_secret = ayon_api.get_secret(
                service_settings["script_key"])

            if isinstance(shotgrid_secret, list):
                raise ValueError(
                    "Shotgrid API Key not found. Make sure to set it in the "
                    "Addon System settings. "
                    "`ayon+settings://shotgrid/service_settings/script_key`"
                )

            self.sg_api_key = shotgrid_secret.get("value")
            if not self.sg_api_key:
                raise ValueError(
                    "Shotgrid API Key not found. Make sure to set it in the "
                    "Addon System settings."
                )

            self.sg_script_name = service_settings["script_name"]
            if not self.sg_script_name:
                raise ValueError(
                    "Shotgrid Script Name not found. Make sure to set it in "
                    "the Addon System settings."
                )

            try:
                self.sg_polling_frequency = int(
                    service_settings["polling_frequency"]
                )
            except Exception:
                self.sg_polling_frequency = 10

            self.custom_attribs_map = {
                attr["ayon"]: attr["sg"]
                for attr in self.settings["compatibility_settings"]["custom_attribs_map"]
                if attr["sg"]
            }
            self.custom_attribs_types = {
                attr["sg"]: (attr["type"], attr["scope"])
                for attr in self.settings["compatibility_settings"]["custom_attribs_map"]
                if attr["sg"]
            }
            self.sg_enabled_entities = self.settings["compatibility_settings"]["shotgrid_enabled_entities"]

            if not all([self.sg_url, self.sg_script_name, self.sg_api_key]):
                msg = "Addon is missing settings, check " \
                      "'AYON > Studio Settings > Shotgrid' and fill out all the fields."
                self.log.error(msg)
                raise ValueError(msg)

        except Exception as e:
            self.log.error("Unable to get Addon settings from the server.")
            self.log.error(traceback.format_exc())
            raise e

        self.handlers_map = self._get_handlers()
        if not self.handlers_map:
            self.log.error("No handlers found for the processor, aborting.")

    def _get_handlers(self):
        """ Import the handlers found in the `handlers` directory.

        Scan the `handlers` directory and build a dictionary with
        each `REGISTER_EVENT_TYPE` found in importable Python files,
        wich get stored as a list, since several handlers could be
        triggered by the same event type.
        """
        handlers_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "handlers"
        )
        handlers_dict = {}

        for root, handlers_directories, handler_files in os.walk(handlers_dir):
            for handler in handler_files:
                if handler.endswith(".py") and not handler.startswith((".", "_")):
                    module_name = str(handler.replace(".py", ""))
                    module_obj = types.ModuleType(module_name)

                    module_loader = importlib.machinery.SourceFileLoader(
                        module_name,
                        os.path.join(root, handler)
                    )
                    module_loader.exec_module(module_obj)
                    register_event_types = module_obj.REGISTER_EVENT_TYPE

                    for event_type in register_event_types:
                        handlers_dict.setdefault(
                            event_type, []
                        ).append(module_obj)

        return handlers_dict

    def get_sg_connection(self):
        """Ensure we can talk to AYON and Shotgrid.

        Start connections to the APIs and catch any possible error, we abort if
        this steps fails for any reason.
        """

        if self._sg is None:
            try:
                self._sg = shotgun_api3.Shotgun(
                    self.sg_url,
                    script_name=self.sg_script_name,
                    api_key=self.sg_api_key
                )
            except Exception as e:
                self.log.error("Unable to create Shotgrid Session.")
                raise e

        try:
            self._sg.connect()

        except Exception as e:
            self.log.error("Unable to connect to Shotgrid.")
            raise e

        return self._sg

    def start_processing(self):
        """Enroll AYON events of topic `shotgrid.event`

        We query AYON Events in search of unfinished `shotgrid.event` events,
        these events must an `action` key in their `payload` in order to be
        processed, that `action` is the one used to match with a `handler`'s
        `REGISTER_EVENT_TYPE` attribute.

        For example, an event that has `{"action": "create-project"}` payload,
        will trigger the `handlers/project_sync.py` since that one has the
        attribute REGISTER_EVENT_TYPE = ["create-project"]
        """
        while True:
            try:
                event = ayon_api.enroll_event_job(
                    "shotgrid.event*",
                    "shotgrid.proc",
                    socket.gethostname(),
                    description="Enrolling to any `shotgrid.event` Event...",
                    max_retries=2,
                    sequential=True,
                )

                if not event:
                    time.sleep(self.sg_polling_frequency)
                    continue

                # Get source event because it is having payload to process
                source_event = ayon_api.get_event(event["dependsOn"])
                payload = source_event["payload"]
                summary = source_event["summary"]

                if source_sg_event_id := summary.get("sg_event_id"):
                    event_id_text = (
                        f". Shotgrid Event ID: {source_sg_event_id}."
                    )
                else:
                    event_id_text = "."

                if not payload:
                    # TODO: maybe remove this - unrealistic scenario
                    ayon_api.update_event(
                        event["id"],
                        description=(
                            f"Unable to process the event{event_id_text} > "
                            f"<{source_event['id']}> since it has no "
                            "Shotgrid Payload!"
                        ),
                        status="finished"
                    )
                    continue

                failed = False
                for handler in self.handlers_map.get(payload["action"], []):
                    # If theres any handler "subscribed" to this event type..
                    try:
                        self.log.info(f"Running the Handler {handler}")
                        ayon_api.update_event(
                            event["id"],
                            description=(
                                "Processing event with Handler "
                                f"{payload['action']}..."
                            ),
                            status="in_progress",
                        )
                        self.log.debug(
                            f"processing event {pformat(payload)}")
                        handler.process_event(
                            self,
                            payload,
                        )
                    except MissingParentError:
                        failed = True
                        ayon_api.update_event(
                            event["id"],
                            status="failed",
                            description=(
                                "An error ocurred while processing "
                                f"{event_id_text}, will be retried"
                            ),
                            payload={
                                "message": traceback.format_exc(),
                            },
                            retries=999
                        )
                        if source_event["topic"] != self._RETRIGGERED_TOPIC:
                            self.log.error(
                                f"Reprocess handler {handler.__name__}, "
                                "will be retried in new order",
                            )

                            # to limit primary key violation
                            new_event_hash = get_event_hash(
                                self._RETRIGGERED_TOPIC,
                                f"{payload['sg_payload']['id']}_dummy"
                            )
                            desc = (source_event['description'].
                                    replace("Leeched", "Recreated"))
                            ayon_api.dispatch_event(
                                self._RETRIGGERED_TOPIC,
                                sender=socket.gethostname(),
                                payload=payload,
                                summary=summary,
                                description=desc,
                                event_hash=new_event_hash
                            )
                        else:
                            self.log.warning("Source event already failed, "
                                             "won't be retried again.")
                    except Exception:
                        failed = True
                        self.log.error(
                            f"Unable to process handler {handler.__name__}",
                            exc_info=True
                        )
                        ayon_api.update_event(
                            event["id"],
                            status="failed",
                            description=(
                                "An error occurred while processing"
                                f"{event_id_text}"
                            ),
                            payload={
                                "message": traceback.format_exc(),
                            },
                        )

                if not failed:
                    self.log.info(
                        "Event has been processed... setting to finished!")

                    ayon_api.update_event(
                        event["id"],
                        description=f"Event processed successfully{event_id_text}",
                        status="finished",
                    )

            except Exception:
                self.log.error(traceback.format_exc())


def service_main():
    ayon_api.init_service()

    shotgrid_processor = ShotgridProcessor()
    sys.exit(shotgrid_processor.start_processing())
