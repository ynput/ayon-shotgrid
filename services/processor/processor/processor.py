"""
A Shotgird Events listener processor for Ayon.

This service will continually run and query the Ayon Events Server in orther to
entroll the events of topic `shotgrid.leech` to perform processing of Shotgrid
related events.
"""
import importlib
import os
import time
import types
import socket

import ayon_api
from nxtools import logging, log_traceback


class ShotgridProcessor:
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
        logging.info("Initializing the Shotgrid Processor.")

        self.handlers_map = None

        try:
            self.settings = ayon_api.get_addon_settings(
                os.environ["AYON_ADDON_NAME"],
                os.environ["AYON_ADDON_VERSION"]
            )

            self.sg_url = self.settings["shotgrid_server"]
            self.sg_script_name = self.settings["shotgrid_script_name"]
            self.sg_api_key = self.settings["shotgrid_api_key"]

            try:
                self.sg_polling_frequency = int(
                    self.settings["service_settings"]["polling_frequency"]
                )
            except Exception:
                self.sg_polling_frequency = 10

            if not all([self.sg_url, self.sg_script_name, self.sg_api_key]):
                msg = "Addon is missing settings, check " \
                      "'AYON > Studio Settings > Shotgrid' and fill out all the fields."
                logging.error(msg)
                raise ValueError(msg)

        except Exception as e:
            logging.error("Unable to get Addon settings from the server.")
            log_traceback(e)
            raise e

        self.handlers_map = self._get_handlers()
        if not self.handlers_map:
            logging.error("No handlers found for the processor, aborting.")
        else:
            logging.debug(f"Found the these handlers: {self.handlers_map}")

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

    def start_processing(self):
        """Enroll AYON events of topic `shotgrid.event`

        We query AYON Events in search of unfinished `shotgrid.event` events,
        these events must an `action` key in their `payload` in order to be
        processed, that `action` is the one used to match with a `handler`'s
        `REGISTER_EVENT_TYPE` attribute.

        For example, an event that has `{"action": "create-project"}` payload,
        will trigger the `handlers/project_sync.py` since that one has the attribute
        REGISTER_EVENT_TYPE = ["create-project"]
        """
        logging.info("Start enrolling for Ayon `shotgrid.event` Events...")

        while True:
            logging.info("Querying for new `shotgrid.event` events...")
            try:
                event = ayon_api.enroll_event_job(
                    "shotgrid.event",
                    "shotgrid.proc",
                    socket.gethostname(),
                    description="Shotgrid Event processing",
                )

                if not event:
                    logging.info("No event of origin `shotgrid.event` is pending.")
                    time.sleep(self.sg_polling_frequency)
                    continue

                source_event = ayon_api.get_event(event["dependsOn"])
                payload = source_event["payload"]

                if not payload:
                    time.sleep(self.sg_polling_frequency)
                    ayon_api.update_event(event["id"], status="finished")
                    ayon_api.update_event(source_event["id"], status="finished")
                    continue

                for handler in self.handlers_map.get(payload["action"], []):
                    # If theres any handler "subscirbed" to this event type..
                    try:
                        logging.info(f"Running the Handler {handler}")
                        handler.process_event(
                            self.sg_url,
                            self.sg_script_name,
                            self.sg_api_key,
                            **payload,
                        )

                    except Exception as e:
                        logging.error(f"Unable to process handler {handler.__name__}")
                        log_traceback(e)
                        ayon_api.update_event(event["id"], status="finished")
                        ayon_api.update_event(source_event["id"], status="finished")

                logging.info("Event has been processed... setting to finished!")
                ayon_api.update_event(event["id"], status="finished")
                ayon_api.update_event(source_event["id"], status="finished")

            except Exception as err:
                log_traceback(err)

            logging.info(
                f"Waiting {self.sg_polling_frequency} seconds..."
            )
            time.sleep(self.sg_polling_frequency)
