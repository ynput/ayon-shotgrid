import sys
import logging
from .processor import ShotgridProcessor

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    shotgrid_processor = ShotgridProcessor()
    sys.exit(shotgrid_processor.start_processing())
