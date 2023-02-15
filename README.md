# Shotgrid integration for Ayon

This project provides three elements for the Ayon pipeline:
 * server/ - The Ayon Backend Addon. - https://github.com/ynput/ayon-addon-template/blob/main/README.md
 * client/ - The Ayon (currently OpenPype) desktop integration.
 * services/ - Standalone dockerized daemons that act based on events (aka `leecher` and `processors`).

The `shotgrid_common` directory contains re-usable code for both `server` and `client`.

## Server
Once loaded into the backend, two new attiributes should be available for the {scope} entities, and the plugin itself can be configured from the Project Settings page: `{ayon_url}/projectManager/projectSettings`, where you can specify your Shotgrid instance URL.

### Hooks
 * Prepare Project - Will ensure the Ayon project contains the necessary elements.
 * Sync from Shotgrid - Will compare the project against the Shotgrid instance, and will ensure both are equal. This **only** creates elements, it does not delete.

### Settings
Here you'll be able to provide a "Script Name" and an API key so Ayon can interact with Shotgrid.

## Client
Currently a copy-paste of OpenPype's `openpype/modules/shotgrid` module, sans the "server" part, which is now handled by the `services`.

## Services
Currently only the `leecher` is implemented, which upon launching, will periodically query the Shotgrid database in search of new Events to process.

## Usage
To create a "server-ready" package of the `server` folder, on a terminal, run `python create_package.py` and a new directory will appear in the `dist` directory (it will be created if it doesnt exist) and you can upload to the server.

You then have to run somewhere the `leecher` service, with the use of podman/docker, which will be the one sending **events** to Ayon server.
 ```
 cd {ayon-shotgrid-addon}/services/leecher
 docker-compose up -d
 ```

By default, the above described Hooks will be triggered by leecher events, but we also have the option to trigger manual syncronization, you can do so by navigating to the project you want to sync:
 `{ayon_url}/projects/{project_name}/addon/shotgrid` where you'll be able to trigger a Sync of the Shotgrid -> Ayon project, with the option to override any differences.

# TODO
 - [] Create addon frontend
 - [] Set up "processors" events.
 - [] Implement "Update from Shotgrid" method in `server/`.
 - [] Marshall openpype implementation to work with `ayon`.
 - [] Ensure `leecher` is using the correct addon settings for connection.
