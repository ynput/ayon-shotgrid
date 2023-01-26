import sys

from .listener import ShotgridProcessor


if __name__ == "__main__":
    shotgird_processor = ShotgridProcessor()
    sys.exit(shotgird_processor.start_processing())

