import socket
from typing import Any, Type

from ayon_server.addons import BaseServerAddon
from ayon_server.api.dependencies import dep_current_user, dep_project_name
from ayon_server.lib.postgres import Postgres
from ayon_server.events import dispatch_event

from nxtools import logging

from .settings import ShotgridSettings, DEFAULT_VALUES
from .version import __version__


SG_ID_ATTRIB = "shotgridId"
SG_PATH_ATTRIB = "shotgridPath"


class ShotgridAddon(BaseServerAddon):
    name = "shotgrid"
    title = "Shotgrid"
    version = __version__
    settings_model: Type[ShotgridSettings] = ShotgridSettings

    frontend_scopes: dict[str, Any] = {"project": {"sidebar": "hierarchy"}}

    def initialize(self):
        logging.info("Initializing Shotgrid Addon.")
        loggin.info("Added Create Attributes Endpoint.")
        self.add_endpoint(
            "sync-from-shotgrid/{project_name}",
            self.get_random_folder,
            method="GET",
        )

    async def _dispatch_create_attributes_event(
        self,
        user: UserEntity = Depends(dep_current_user),
        project_name: str = Depends(dep_project_name),
    ):
        payload = {}
        ayon_api.dispatch_event(
            "shotgrid.leech",
            sender=socket.gethostname(),
            event_hash=payload["id"],
            project_name=None,
            username=user_name,
            description=description,
            summary=None,
            payload=payload,
        )
        logging.info("Dispatched event", payload['event_type'])

        dispatch_event(
            "shotgrid.leech",
            *,
            sender: str | None = None,
            hash: str | None = None,
            project: str | None = None,
            user: str | None = None,
            depends_on: str | None = None,
            description: str | None = None,
            summary: dict | None = None,
            payload: dict | None = None,
            finished: bool = True,
            store: bool = True,
        ) 


    async def get_default_settings(self):
        logging.info(f"Loading default Settings for {self.name} addon.")
        settings_model_cls = self.get_settings_model()
        return settings_model_cls(**DEFAULT_VALUES)

    async def setup(self):
        logging.info(f"Performing {self.name} addon setup.")
        need_restart = await self.create_shotgrid_attributes()
        if need_restart:
            logging.info("Created new attributes in database, requesting server to restart.")
            self.request_server_restart()

    async def create_shotgrid_attributes(self) -> bool:
        """Make sure there are required attributes which ftrack addon needs.

        Returns:
            bool: 'True' if an attribute was created or updated.
        """

        query = (
            "SELECT name, position, scope, data from public.attributes "
            f"WHERE (name = '{SG_ID_ATTRIB}' OR name = '{SG_PATH_ATTRIB}') "
            "AND (scope = '{project, folder, task}')"
        )

        if Postgres.pool is None:
            await Postgres.connect()

        shotgrid_attributes = await Postgres.fetch(query)
        all_attributes = await Postgres.fetch(
            "SELECT name from public.attributes"
        )
        logging.info("Querying database for existing attributes...")
        logging.debug(shotgrid_attributes)

        if shotgrid_attributes:
            logging.info("Shotgrid Attributes already exist in database!")
            return False

        postgres_query = "\n".join((
            "INSERT INTO public.attributes",
            "    (name, position, scope, data)",
            "VALUES",
            "    ($1, $2, $3, $4)",
            "ON CONFLICT (name)",
            "DO UPDATE SET",
            "    scope = $3,",
            "    data = $4",
        ))
        logging.info("Creating Shotgrid Attributes...")

        await Postgres.execute(
            postgres_query,
            SG_ID_ATTRIB,  # name
            len(all_attributes) + 1,  # Add Attributes at the end of the list
            ["project", "folder", "task"],  # scope
            {
                "type": "string",
                "title": "Shotgrid ID",
                "description": "The ID in the Shotgrid Instance."
            }
        )

        await Postgres.execute(
            postgres_query,
            SG_PATH_ATTRIB,  # name
            len(all_attributes) + 2,  # Add Attributes at the end of the list 
            ["project", "folder", "task"],  # scope
            {
                "type": "string",
                "title": "Shotgrid Path",
                "decription": "The path in the Shotgrid Instance."
            }
        )

        return True

