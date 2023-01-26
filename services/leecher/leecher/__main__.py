import sys

from .listener import ShotgridListener


if __name__ == "__main__":
    shotgird_listener = ShotgridListener()
    sys.exit(shotgird_listener.start_listening())

