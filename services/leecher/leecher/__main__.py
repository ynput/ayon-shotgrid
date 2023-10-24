import sys

from .listener import ShotgridListener


if __name__ == "__main__":
    shotgrid_listener = ShotgridListener()
    sys.exit(shotgrid_listener.start_listening())

