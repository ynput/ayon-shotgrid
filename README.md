# Shotgrid integration for Ayon

This project provides three elements for the Ayon pipeline:
 * server/ - The Ayon Backend Addon.
 * client/ - The Ayon (currently OpenPype) desktop integration.
 * services/ - Standalone dockerized daemons that act based on events (aka `leecher` and `processors`).

In order to use this integrations you'll need to run the `python create_package.py` script which will create a `zip` file with the current version (the number is defined in `version.py`) in `ayon-shotgrid/package/shotgrid-{addon version}.zip`, you can then upload this zip file in your AYON instance, on the Bundles (`/settings/bundles`) section, make sure you restart the server, AYON should prompt you to do so after uploading.

## Server
Once the instance has restarted, you should be able to enable the addon by going into the `Settings > Bundles` and create (or duplicate an existing) bundle, where you can now choose `shotgrid` and the `version` you installed; make sure you set the bundle as `Production`.
If the Addon loaded succesfully you should be able to see a new tab in your `Settings > Shotgrid`.

For the Shotgrid integration to work, we need to provide several information, firstly we'll a Shotgrid Script and it's API key, refer to the [Shotgrid Documentation](https://developer.shotgridsoftware.com/99105475/?title=Create+and+manage+API+scripts) to create one; take note of the info and in AYON, navigate to the `Settings > Secrets` page, create a new secret with the `script_name` as the "Secret Name" and the `script_api_key` as the "Secret Value".

We can now go into the `Settings > Studio settings > Shotgrid` page in AYON and fill up the following fields:
 * Shotgrid URL - This will be the URL to your Shotgrid instance.
 * Shotgrid API Secret - Select the secret you created in the previous step.
 * Shotgrid field for the Project Code - A field in the `Project` entity that hold the project code, can be an existing one or a new one, default is `code`.
 * Service Settings > How often (in seconds) to query the Shotgrid Database  - Defaults to 10 seconds, time between `leeching`, `processing` and `transmitting` operations.


## Desktop application
When launching Ayon for the first time you'll be asked to provide a login (only the username) for Shotgrid, this is the user that will be used for publishing.
After providing a login people can publish normally, the integartion will ensure that the user can connect to Shotgrid, that has the correct permissions and will create the Version and PublishedFile in Shotgrid if the publish is succesful.

## Services
The services are a way to handle operations between AYON and Shotgrid in the background, these have been developed around the AYON Events system, we replicate Shotgrid events (the ones we care) as AYON `shotgrid.event`; which then the `processor` will pick up and process them acordingly; lastly the `transmitter` will look for changes in AYON and attempt to replicate them in Shotgrid.
In any case, the Shotgrid project has to have the field "Ayon Auto Sync" enabled for the `leecher` and the `transmitter` to work.
They share code, which is found in `shotgrid_common`, most importantly the `AyonShotgridHub` a class that bootstraps common action when working with AYON and Shotgrid.

The three provided services are:
 * `processor` - This has a set of handlers for different `shotgrid.event` and act on.
 * `leecher` - Periodically queries the `EventLogEntry` table on Shotgrid and ingests any event that interests us dispatching it as a `shotgrid.event`, this will only query projects that have the "Ayon Auto Sync" field enabled.
 * `transmitter` - Periodically check for new events in AYON of topic `entity.*`, and push any changes to Shotgrid, only affects to projects that have the "Ayon Auto Sync" field enabled.

The most straighforward way to get this up and running is by using ASH (Ayon Service Host), after loading the Addon on the server, you should be able to spawn services in the "Services" page.

### Development
There's a single `Makefile` at the root of the `services` folder, which is used to `build` the docker images and to run the services locally with the `dev` target, this is UNIX only for the time being, running `make` without argument will print information as to how to run use it.

#### Building Docker Images
To build the docker images you can run `make SERVICE=<service-name> build`, so for example, to build the `processor` you'd do `make SERVICE=processor build`, this will build and tag the local image, with the version found in `version.py` at the root of the addon.

#### Running the Service locally
In order to run the service locally we need to specify certain environment variables, to do so, copy the `sample_env` file, rename to `.env` and fill the fields acordingly:
```
AYON_API_KEY=<AYON_API_KEY> # You can create a `service` user in Ayon, and then get the Key from there.
AYON_SERVER_URL=<YOUR_AYON_URL>
PYTHONDONTWRITEBYTECODE=1
```

We are ready to spin up the service, for convinience we got a `make` target for this:
```sh
make SERVICE=<service-name> dev
```

You should now see something similar to:
```sh
INFO       Initializing the Shotgrid Processor.
DEBUG      Found these handlers: {'create-project': [<module 'project_sync'>], 'sync-from-shotgrid': [<module 'sync_from_shotgrid'>], 'shotgrid-event': [<module 'update_from_shotgrid'>]}
INFO       Start enrolling for Ayon `shotgrid.event` Events...
INFO       Querying for new `shotgrid.event` events...
INFO       No event of origin `shotgrid.event` is pending. 
```

### Makefile commands
For those who cannot use `Makefiles` here are the commands that are required to perfomr the same action as with `make`, using the `processor` version `0.2.` as example, from the `services` folder:

Building the docker image:
 ```sh
 docker build -t ynput/ayon-shotgrid-processor:0.2.1 -f processor/Dockerfile .
```

Running a service locally:
```sh
docker run --rm -u ayonuser -ti \
  -v services/shotgrid_common:services/shotgrid_common:Z \
  -v services/processor:/service:Z \
  --env-file services/processor/.env \
  --env AYON_ADDON_NAME=shotgrid \
  --env AYON_ADDON_VERSION=0.2.1 \
  --attach=stdin \
  --attach=stdout \
  --attach=stderr \
  --network=host \
  ynput/ayon-shotgrid-processor:0.2.1 python -m processor
```
This one is trickier since the make file will symlink the `shotgrid_common` inside the `service/processor` folder.

### Running it without docker or make
You don't need to run these as dockerized scripts, for that you'll need either [Poetry](https://python-poetry.org/) installed and create an environment specified by the `pyproject.toml` or using `virtualenv` and install the packages specified in the `[tool.poetry.dependencies]` section of the `pyproject.toml`; once in that environment you'll need to load the contents of the `.env` file and finally:
```sh
python -m processor
```

# Usage
With this Integration you can perform the following actions by navigating to `AYON >Settings > Shotgrid`, and loading all projects by clicking `Populate Data`:

## Import a New Shotgrid Project
With the `processor` service running, synchronize `Shotgrid --> AYON` will replicate the Shotgrid structure in AYON.

## Export an AYON project into Shotgrid
With the `processor` service running, synchronize `AYON --> Shotgrid` will replicate the AYON structure in Shotgrid.

## Update based on Shotgrid Events
With the `leecher` **and** the `processor` services running, and the `Ayon Auto Sync` field **enabled** in Shotgrid, whenever an event on `Episodes`, `Sequences`, `Shots`` or `Tasks` occurs, an event will be dispatched in Ayon `shotgrid.event` this event will be then processed in another event `shotgrid.proc` dispatched by the `processor` service; this currently creates and removes entities, and updates the name of entities so they are in sync between Shotgrid and Ayon.

## Update based on AYON Events
With the `transmitter` **and** the `processor` services running, and the `Ayon Auto Sync` field **enabled** in Shotgrid, whenever an event on `entity.*` occurs in AYON, an event will be dispatched in Ayon `shotgrid.push` this event will attempt to replicate the changes made in AYON in Shotgrid.

In all instances you'll want to keep an eye on the terminal where you launched the services, where you can track the progress of any of the handlers. This will be imporved in teh future so it can be tracked from AYON.

