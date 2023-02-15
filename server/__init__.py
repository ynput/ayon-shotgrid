from typing import Any, Type

from ayon_server.addons import BaseServerAddon
from ayon_server.lib.postgres import Postgres

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
        logging.info(shotgrid_attributes)

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

