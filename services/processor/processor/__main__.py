import sys

from .processor import ShotgridProcessor


if __name__ == "__main__":
    shotgird_processor = ShotgridProcessor()
    sys.exit(shotgird_processor.start_processing())

