import os
import sys
import logging
import argparse
import subprocess
import time

from ayon_api.constants import (
    DEFAULT_VARIANT_ENV_KEY,
)

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_all():
    all_idx = sys.argv.index("all")
    leecher_args = list(sys.argv)
    processor_args = list(sys.argv)
    transmitter_args = list(sys.argv)

    leecher_args[all_idx] = "leecher"
    processor_args[all_idx] = "processor"
    transmitter_args[all_idx] = "transmitter"

    leecher_args.insert(0, sys.executable)
    processor_args.insert(0, sys.executable)
    transmitter_args.insert(0, sys.executable)

    leecher = subprocess.Popen(leecher_args)
    processor = subprocess.Popen(processor_args)
    transmitter = subprocess.Popen(transmitter_args)
    try:
        while True:
            l_poll = leecher.poll()
            p_poll = processor.poll()
            t_poll = transmitter.poll()
            if (
                l_poll is not None
                and p_poll is not None
                and t_poll is not None
            ):
                break

            if (
                l_poll is not None
                or p_poll is not None
                or t_poll is not None
            ):
                if l_poll is not None:
                    leecher.kill()
                if p_poll is not None:
                    processor.kill()
                if t_poll is not None:
                    transmitter.kill()

            time.sleep(0.1)
    finally:
        if leecher.poll() is None:
            leecher.kill()

        if processor.poll() is None:
            processor.kill()

        if transmitter.poll() is None:
            transmitter.kill()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--service",
        help="Run processor service",
        choices=["processor", "leecher", "transmitter", "all"],
    )
    parser.add_argument(
        "--variant",
        default="production",
        help="Settings variant",
    )
    opts = parser.parse_args()
    if opts.variant:
        os.environ[DEFAULT_VARIANT_ENV_KEY] = opts.variant

    service_name = opts.service
    if service_name == "all":
        return run_all()

    for path in (
        os.path.join(ADDON_DIR, "services", "shotgrid_common"),
        os.path.join(ADDON_DIR, "services", service_name),
    ):
        sys.path.insert(0, path)

    if service_name == "processor":
        from processor import ShotgridProcessor

        shotgrid_processor = ShotgridProcessor()
        sys.exit(shotgrid_processor.start_processing())

    elif service_name == "leecher":
        from leecher import ShotgridListener

        shotgrid_listener = ShotgridListener()
        sys.exit(shotgrid_listener.start_listening())

    else:
        from transmitter import ShotgridTransmitter

        shotgrid_transmitter = ShotgridTransmitter()
        sys.exit(shotgrid_transmitter.start_processing())


if __name__ == "__main__":
    logging.basicConfig()
    main()
