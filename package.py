name = "shotgrid"
title = "Shotgrid"
version = "0.6.9"
client_dir = "ayon_shotgrid"

services = {
    "ShotgridLeecher": {
        "image": f"ynput/ayon-shotgrid-leecher:{version}"},
    "ShotgridProcessor": {
        "image": f"ynput/ayon-shotgrid-processor:{version}"},
    "ShotgridTransmitter": {
        "image": f"ynput/ayon-shotgrid-transmitter:{version}"},
}
ayon_required_addons = {
    "core": ">=0.3.0",
}
ayon_compatible_addons = {}
