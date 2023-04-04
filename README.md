# Shotgrid integration for Ayon

This project provides three elements for the Ayon pipeline:
 * server/ - The Ayon Backend Addon. - https://github.com/ynput/ayon-addon-template/blob/main/README.md
 * TODO: client/ - The Ayon (currently OpenPype) desktop integration.
 * services/ - Standalone dockerized daemons that act based on events (aka `leecher` and `processors`).

## Server
This is the part that needs to be uplaoded (or copied) to the `/backend/addons/` directory of your Ayon instance, as a helper, you can run the following command:
`python create_package.py` from the root of this project; which will create a folder `package` and you can copy the **contents** of that into the `addons` folder of your Ayon isntance.

Once copied, and the instance restarted, you should be able to enable the addon by going into the `Settings > Addon Version > Shotgrid Sync` and choosing `0.0.1` in the `Production` dropdown.
If the Addon loaded succesfully you should be able to see a new tab in your `Settings > Shotgrid Sync`.

Before we can do anything we need to fill some information in the `Settings > Studio settings > Shotgrid Sync` page, we need the Shotgrid URL, a script name and a Shotgrid API key of said script, to set this up refer to the [Shotgrid Documentation](https://developer.shotgridsoftware.com/99105475/?title=Create+and+manage+API+scripts), after creating one, jsut fill the corresponding fields.


## Services
There are two services that the Addon requires to perform any activity:
 * `processor` - This has a set of handlers for different `shotgrid.event` and act on those.
 * `leecher` - Periodically queries the `EventLogEntry` table on Shotgrid and ingests any event that interstes us dispatching it as a `shotgird.event`.

To get any of these two running, navigate to their respective folder, and we'll use `make` to build a `Docker` iamge that will run our services.
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

We are ready to spin up the service, for convinience we got a `make` commadn for this:
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
With this Addon you can perform the following actions:

## Import a New Shotgrid Project
With the `processor` service running, you can go to the `Settings > Shotgrid Sync` page, and after waiting some seconds, the dropdown under `Choose a Shotgrid Project:` should change from `Fetching Shotgrid projects...` to `Choose a Project to Import and Sync...` you'll then be able to choose any Shotgrid project that matches the specified requirements.

## Manage Existing Shotgrid Projects
With the `processor` service running, you can go to the `Settings > Shotgrid Sync` page, and after waiting some seconds, the dropdown under `Already imported Projects` at the right side of the page will be loaded with existing projects, select it and press `Sync Shotgrid Project`; this will trigger a full syncronization for projects we already imported (it already exists in Ayon), only adding any missing entity from Shotgrid to Ayon.

## Update based on Shotgrid Events
With the `leecher` **and** the `processor` services running, and the `Ayon Auto Sync` field **enabled** in Shotgrid, whenever an event on `Episodes`, `Sequences`, `Shots`` or `Tasks` occurs, an event will be dispatched in Ayon `shotgrid.event` this event will be then processed in another event `shotgrid.proc` dispatched by the `processor` service; this currently creates and removes entities, and updates the name of entities so they are in sync between Shotgrid and Ayon.

In all instances you'll want to keep an eye on the terminal where you launched the `processor` where you can track the progress of any of the handlers.

