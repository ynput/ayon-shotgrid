# Shotgrid integration for AYON

This project provides three elements for the AYON pipeline:

* server/ - The AYON Backend Addon.
* frontend/ - The AYON server Shotgrid settings tab.
* client/ - The AYON desktop integration.
* services/ - Standalone dockerized daemons that act based on events (aka `leecher` and `processors`).

In order to use this integration, you'll need to run the `python create_package.py` script, which will create a `zip` file with the current version (the number is defined in `package.py`) in `ayon-shotgrid/package/shotgrid-{addon version}.zip`. You can then upload this zip file in your AYON instance, on the Bundles (`/settings/bundles`) section. Make sure you restart the server. AYON should prompt you to do so after uploading.

## Server
Once the instance has restarted, you should be able to enable the addon by going into the `Settings > Bundles` and creating (or duplicating an existing) bundle, where you can now choose `shotgrid` and the `version` you installed. Make sure you set the bundle as `Production`.
If the addon loaded successfully, you should be able to see a new tab in your `Settings > Shotgrid`.

For the Shotgrid integration to work, we need to provide several pieces of information. Firstly, we’ll need a Shotgrid Script and its API key. Refer to the [Shotgrid Documentation](https://developer.shotgridsoftware.com/99105475/?title=Create+and+manage+API+scripts) to create one; take note of the information and in AYON, navigate to the `Settings > Secrets` page. Create a new secret with the `script_name` as the "Secret Name" and the `script_api_key` as the "Secret Value".

We can now go into the `Settings > Studio settings > Shotgrid` page in AYON and fill in the following fields:
* Shotgrid URL - This will be the URL to your Shotgrid instance.
* Shotgrid API Secret - Select the secret you created in the previous step.
* Shotgrid field for the Project Code - A field in the `Project` entity that holds the project code. It can be an existing one or a new one. The default is `code`.
* Service Settings > How often (in seconds) to query the Shotgrid Database  - Defaults to 10 seconds, the time between `leeching`, `processing`, and `transmitting` operations.

## Desktop application
When launching AYON for the first time, you'll be asked to provide a login (only the username) for Shotgrid. This is the user that will be used for publishing.
After providing a login, people can publish normally. The integration will ensure that the user can connect to Shotgrid, has the correct permissions, and will create the Version and PublishedFile in Shotgrid if the publish is successful.

## Services
The services are a way to handle operations between AYON and Shotgrid in the background. These have been developed around the AYON Events system. We replicate Shotgrid events (the ones we care about) as AYON `shotgrid.event`, which then the `processor` will pick up and process them accordingly. Lastly, the `transmitter` will look for changes in AYON and attempt to replicate them in Shotgrid.
In any case, the Shotgrid project has to have the field "Ayon Auto Sync" enabled for the `leecher` and the `transmitter` to work.
They share code, which is found in `shotgrid_common`. Most importantly, the `AyonShotgridHub` is a class that bootstraps common actions when working with AYON and Shotgrid.

The three provided services are:

* `processor` - This has a set of handlers for different `shotgrid.event` and acts on them.
* `leecher` - Periodically queries the `EventLogEntry` table on Shotgrid and ingests any event that interests us, dispatching it as a `shotgrid.event`. This will only query projects that have the "Ayon Auto Sync" field enabled.
* `transmitter` - Periodically checks for new events in AYON of topic `entity.*` and pushes any changes to Shotgrid, only affecting projects that have the "Ayon Auto Sync" field enabled.

The most straightforward way to get this up and running is by using ASH (AYON Service Host). After loading the Addon on the server, you should be able to spawn services in the "Services" page.

### Development
There's a single `Makefile` at the root of the `services` folder, which is used to `build` the Docker images and to run the services locally with the `dev` target. This is UNIX only for the time being. Running `make` without arguments will print information as to how to run and use it.

#### Building Docker Images
To build the Docker images, you can run `make SERVICE=<service-name> build`. So, for example, to build the `processor`, you'd do `make SERVICE=processor build`. This will build and tag the local image, with the version found in `package.py` at the root of the addon.

#### Running the Service locally
In order to run the service locally, we need to specify certain environment variables. To do so, copy the `sample_env` file, rename it to `.env`, and fill the fields accordingly:

```
AYON_API_KEY=<AYON_API_KEY> # You can create a `service` user in AYON, and then get the Key from there.
AYON_SERVER_URL=<YOUR_AYON_URL>
PYTHONDONTWRITEBYTECODE=1
```

We are ready to spin up the service. For convenience, we got a `make` target for this:

```sh
make SERVICE=<service-name> dev
```

You should now see something similar to:

```sh
INFO       Initializing the Shotgrid Processor.
DEBUG      Found these handlers: {'create-project': [<module 'project_sync'>], 'sync-from-shotgrid': [<module 'sync_from_shotgrid'>], 'shotgrid-event': [<module 'update_from_shotgrid'>]}
INFO       Start enrolling for AYON `shotgrid.event` Events...
INFO       Querying for new `shotgrid.event` events...
INFO       No event of origin `shotgrid.event` is pending.
```

### Makefile commands

For those who cannot use `Makefiles`, here are the commands that are required to perform the same action as with `make`, using the `processor` version `0.2.` as an example, from the `services` folder:

Building the Docker image:

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

This one is trickier since the Makefile will symlink the `shotgrid_common` inside the `service/processor` folder.

### Running it without docker or make
You don't need to run these as Dockerized scripts; for that, you'll need either [Poetry](https://python-poetry.org/) installed and create an environment specified by the `pyproject.toml` or using `virtualenv` and install the packages specified in the `[tool.poetry.dependencies]` section of the `pyproject.toml`; once in that environment, you'll need to load the contents of the `.env` file and finally:

```sh
python -m processor
```

# Usage
With this integration, you can perform the following actions by navigating to `AYON >Settings > Shotgrid` and loading all projects by clicking `Populate Data`:

## Import a New Shotgrid Project
With the `processor` service running, synchronize `Shotgrid --> AYON` will replicate the Shotgrid structure in AYON.

## Export an AYON project into Shotgrid
With the `processor` service running, synchronize `AYON --> Shotgrid` will replicate the AYON structure in Shotgrid.

## Update based on Shotgrid Events
With the `leecher` **and** the `processor` services running, and the `Ayon Auto Sync` field **enabled** in Shotgrid, whenever an event on `Episodes`, `Sequences`, `Shots`, or `Tasks` occurs, an event will be dispatched in Ayon `shotgrid.event`; this event will be then processed in another event `shotgrid.proc` dispatched by the `processor` service; this currently creates and removes entities and updates the name of entities so they are in sync between Shotgrid and Ayon.

## Update based on AYON Events
With the `transmitter` **and** the `processor` services running, and the `Ayon Auto Sync` field **enabled** in Shotgrid, whenever an event on `entity.*` occurs in AYON, an event will be dispatched in Ayon `shotgrid.push`; this event will attempt to replicate the changes made in AYON in Shotgrid.

In all instances, you'll want to keep an eye on the terminal where you launched the services, where you can track the progress of any of the handlers. This will be improved in the future so it can be tracked from AYON.


# Automated tests

## Requirements

* Your local `python` should be >=3.10
* You need a local AYON server with a service AYON_API_KEY defined

## Run the tests

Windows:
```shell
.\service_tools\manage.ps1 run-tests
```

Linux:
```
./service_tools/make runtests
```
