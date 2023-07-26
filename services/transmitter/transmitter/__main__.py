import sys

from .transmitter import ShotgridTransmitter


if __name__ == "__main__":
    shotgird_transmitter = ShotgridTransmitter()
    sys.exit(shotgird_transmitter.start_processing())

