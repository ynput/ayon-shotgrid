import sys

from .transmitter import ShotgridTransmitter


if __name__ == "__main__":
    shotgrid_transmitter = ShotgridTransmitter()
    sys.exit(shotgrid_transmitter.start_processing())

