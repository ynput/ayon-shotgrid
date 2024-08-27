name = "shotgrid"
title = "Shotgrid"
version = "0.4.4-bpc.1"
client_dir = "ayon_shotgrid"

services = {
    "ShotgridLeecher": {
        "image": "ynput/ayon-shotgrid-leecher:0.4.4"},
    "ShotgridProcessor": {
        "image": "ynput/ayon-shotgrid-processor:0.4.4"},
    "ShotgridTransmitter": {
        "image": "ynput/ayon-shotgrid-transmitter:0.4.4"},
}
ayon_required_addons = {
    "core": ">=0.3.0",
}
ayon_compatible_addons = {}
