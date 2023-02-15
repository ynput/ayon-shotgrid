"""
A Shotgird Events listener processor for Ayon.

This service will continually run and query the Ayon Events Server in orther to
entroll the events of topic `shotgrid.leech` to perform processing of Shotgrid
related events.
"""
import importlib
import os
import sys
import time
import types
import signal
import socket

import ayon_api
from nxtools import logging
import shotgun_api3


class ShotgridProcessor:
    def __init__(self):
        """ Ensure both Ayon and Shotgrid connections are available.

        Set up common needed attributes and handle shotgrid connection
        closure via signal handlers.

        Args:
            func (Callable, None): In case we want to override the default
                function we cast to the processed events.
        """
        logging.info("Initializing the Shotgrid Processor.")

        # Grab all the `handlers` from `processor/handlers` and map them to
        # the events that are meant to trigger them
        self.handlers_map = None

        try:
            self.settings = ayon_api.get_addon_settings(
                os.environ["AY_ADDON_NAME"],
                os.environ["AY_ADDON_VERSION"]
            )
            self.shotgird_url = self.settings["shotgrid_server"]
            self.shotgrid_script_name = self.settings["shotgrid_script_name"]
            self.shotgrid_api_key = self.settings["shotgrid_api_key"]

            try:
                self.shotgrid_polling_frequency = int(
                    self.settings["service_settings"]["polling_frequency"]
                )
            except Exception:
                self.shotgrid_polling_frequency = 10

        except Exception as e:
            logging.error("Unable to get Addon settings from the server.")
            logging.error(e)
            raise e

        try:
            self.shotgrid_session = shotgun_api3.Shotgun(
                self.shotgird_url,
                script_name=self.shotgrid_script_name,
                api_key=self.shotgrid_api_key
            )
            self.shotgrid_session.connect()
        except Exception as e:
            logging.error("Unable to connect to Shotgrid Instance:")
            logging.error(e)
            raise e

        self.handlers_map = self._get_handlers()
        logging.debug(f"Found the these handlers: {self.handlers_map}")
        signal.signal(signal.SIGINT, self._signal_teardown_handler)
        signal.signal(signal.SIGTERM, self._signal_teardown_handler)

    def _signal_teardown_handler(self, signalnum, frame):
        logging.warning("Process stop requested. Terminating process.")
        self.shotgrid_session.close()
        logging.warning("Termination finished.")
        sys.exit(0)

    def _get_handlers(self):
        """ Import the handlers found in the `handlers` directory.

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
        """ Main loop querying the Shotgrid database for new events

        Since Shotgrid does not have an event hub per se, we need to query
        the "EventLogEntry table and send these as Ayon events for processing.
        """

        # Enroll `shotgrid.leech` events
        logging.info("Start enrolling for Ayon `shotgrid.leech` Events...")

        while True:
            logging.info("Querying for new `shotgrid.leech` events...")
            try:
                event = ayon_api.enroll_event_job(
                    "shotgrid.leech",
                    "shotgrid.proc",
                    socket.gethostname(),
                    description="Shotgrid Event processing",
                )

                if not event:
                    logger.info("No event of origin `shotgrid.leech` is pending.")
                    time.sleep(1.5)
                    continue

                source_event = ayon_api.get_event(event["dependsOn"])
                print(source_event)
                if not source_event["payload"]:
                    time.sleep(1.5)
                    ayon_api.update_event(event["id"], status="finished")
                    ayon_api.update_event(source_event["id"], status="finished")
                    continue

                print("hey")
                print(source_event["payload"]["event_type"])
                print(source_event["payload"]["event_type"] in self.handlers_map)

                for handler in self.handlers_map.get(source_event["payload"]["event_type"], []):
                    # If theres any handler "subscirbed" to this event type..
                    try:
                        handler.process_event(
                            self.shotgrid_session,
                            source_event["payload"]
                        )
                    except Exception as e:
                        logging.error(f"Unable to process handler {handler.__name__}")
                        raise e

                logging.info("Event has been processed... setting to finished!")
                ayon_api.update_event(event["id"], status="finished")
                ayon_api.update_event(source_event["id"], status="finished")

            except Exception as err:
                logging.error(err)

            logging.info(
                f"Waiting {self.shotgrid_polling_frequency} seconds..."
            )
            time.sleep(self.shotgrid_polling_frequency)
