import sys

from .processor import ShotgridProcessor


if __name__ == "__main__":
    shotgrid_processor = ShotgridProcessor()
    sys.exit(shotgrid_processor.start_processing())

