# Shotgrid integration for Ayon

This project provides three elements for the Ayon pipeline:
 * server/ - The Ayon Backend Addon.
 * client/ - The Ayon (currently OpenPype) desktop integration.
 * services/ - Standalone dockerized daemons that act based on events (aka `leecher` and `processors`).

In order to use this integrations you'll need to run the `python create_package.py` script which will create a folder with the current version (the number is defined in `version.py`) in `ayon-shotgrid/package/shotgrid/{addon version}`, you then have to upload the `shotgrid` directory (included) into your Ayon instance, in the `/<server root>/addons/shotgrid` path, this should trigger a restart of the server, otherwise do so manually.

## Server
Once the instance has restarted, you should be able to enable the addon by going into the `Settings > Addon Version > Shotgrid Sync` and choosing the version number of the addon you uploaded in the `Production` dropdown.
If the Addon loaded succesfully you should be able to see a new tab in your `Settings > Shotgrid Sync`.

Before proceeding some information has to be provided in the `Settings > Studio settings > Shotgrid Sync` page:
 * Shotgrid URL
 * Shotgrid Script Name
 * Shotgrid API Key

Refer to the [Shotgrid Documentation](https://developer.shotgridsoftware.com/99105475/?title=Create+and+manage+API+scripts) to set these up.

## Desktop application
When launching Ayon for the first time you'll be asked to provide a login (only the username) for Shotgrid, this is the user that will be used for publishing.
After providing a login people can publish normally, the integartion will ensure that the user can connect to Shotgrid, that has the correct permissions and will create the Version and PublishedFile in Shotgrid if the publish is succesful.

## Services
There are two services that the Addon requires to perform any activity:
 * `processor` - This has a set of handlers for different `shotgrid.event` and act on those.
 * `leecher` - Periodically queries the `EventLogEntry` table on Shotgrid and ingests any event that interests us dispatching it as a `shotgird.event`.

To get any of these two running, navigate to their respective folder, we'll use `make` to build a `Docker` image that will run our services.
```sh
cd services/processor
make build # This will create the Container image
```

We need a file called `.env` to pass to the `docker run` command, a `sample_env` has been included, copy and rename to `.env` and fill the fields acordingly:
```
AYON_API_KEY=<AYON_API_KEY> # You can create a `service` user in Ayon, and then get the Key from there.
AYON_SERVER_URL=<YOUR_AYON_URL>
AY_ADDON_NAME=<addon_name>
AY_ADDON_VERSION=<addon_version>
```

We are ready to spin up the service, for convinience we got a `make` command for this:
```sh
make dev
```

You should now see something similar to:
```sh
INFO       Initializing the Shotgrid Processor.
DEBUG      Found the these handlers: {'create-project': [<module 'project_sync'>], 'sync-from-shotgrid': [<module 'sync_from_shotgrid'>], 'shotgrid-event': [<module 'update_from_shotgrid'>]}
INFO       Start enrolling for Ayon `shotgrid.event` Events...
INFO       Querying for new `shotgrid.event` events...
INFO       No event of origin `shotgrid.event` is pending. 
```

That means all is good, same instructions apply for the `leecher` service.

### Running it without docker or make
You don't need to run these as dockerized scripts, for that you'll need either [Poetry](https://python-poetry.org/) installed and create an environment specified by the `pyproject.toml` or using `virtualenv` and install the packages specified in the `[tool.poetry.dependencies]` section of the `pyproject.toml`; once in that environment you'll need to load the contents of the `.env` file and finally:
```sh
python -m processor
```

# Usage
With this Integration you can perform the following actions:

## Import a New Shotgrid Project
With the `processor` service running, you can go to the `Settings > Shotgrid Sync` page, and after waiting some seconds, the dropdown under `Choose a Shotgrid Project:` should change from `Fetching Shotgrid projects...` to `Choose a Project to Import and Sync...` you'll then be able to choose any Shotgrid project that matches the specified requirements.

## Manage Existing Shotgrid Projects
With the `processor` service running, you can go to the `Settings > Shotgrid Sync` page, and after waiting some seconds, the dropdown under `Already imported Projects` at the right side of the page will be loaded with existing projects, select it and press `Sync Shotgrid Project`; this will trigger a full syncronization for projects we already imported (it already exists in Ayon), only adding any missing entity from Shotgrid to Ayon.

## Update based on Shotgrid Events
With the `leecher` **and** the `processor` services running, and the `Ayon Auto Sync` field **enabled** in Shotgrid, whenever an event on `Episodes`, `Sequences`, `Shots`` or `Tasks` occurs, an event will be dispatched in Ayon `shotgrid.event` this event will be then processed in another event `shotgrid.proc` dispatched by the `processor` service; this currently creates and removes entities, and updates the name of entities so they are in sync between Shotgrid and Ayon.

In all instances you'll want to keep an eye on the terminal where you launched the `processor` where you can track the progress of any of the handlers.

