from typing import Any, Type

from ayon_server.addons import BaseServerAddon
from ayon_server.lib.postgres import Postgres
from .settings import ShotgridSettings, DEFAULT_VALUES
from .version import __version__

from nxtools import logging


SG_ID_ATTRIB = "shotgridId"
SG_TYPE_ATTRIB = "shotgridType"


class ShotgridAddon(BaseServerAddon):
    name = "shotgrid"
    title = "Shotgrid Sync"
    version = __version__
    settings_model: Type[ShotgridSettings] = ShotgridSettings

    frontend_scopes: dict[str, Any] = {"settings": {}}

    services = {
        "ShotgridLeecher": {"image": f"ynput/ayon-shotgrid-leecher:{__version__}"},
        "ShotgridProcessor": {"image": f"ynput/ayon-shotgrid-processor:{__version__}"},
        "ShotgridTransmitter": {"image": f"ynput/ayon-shotgrid-transmitter:{__version__}"},
    }

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
        """Make sure Ayon has the `shotgridId` and `shotgridPath` attributes.

        Returns:
            bool: 'True' if an attribute was created or updated.
        """

        query = (
            "SELECT name, position, scope, data from public.attributes "
            f"WHERE (name = '{SG_ID_ATTRIB}' OR name = '{SG_TYPE_ATTRIB}') "
            "AND (scope = '{project, folder, task}')"
        )

        if Postgres.pool is None:
            await Postgres.connect()

        shotgrid_attributes = await Postgres.fetch(query)
        all_attributes = await Postgres.fetch(
            "SELECT name from public.attributes"
        )
        logging.debug("Querying database for existing attributes...")
        logging.debug(shotgrid_attributes)

        if shotgrid_attributes:
            logging.debug("Shotgrid Attributes already exist in database!")
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
        logging.debug("Creating Shotgrid Attributes...")

        await Postgres.execute(
            postgres_query,
            SG_ID_ATTRIB,  # name
            len(all_attributes) + 1,  # Add Attributes at the end of the list
            ["project", "folder", "task"],  # scope
            {
                "type": "string",
                "title": "Shotgrid ID",
                "description": "The ID in the Shotgrid Instance.",
                "inherit": "False"
            }
        )

        await Postgres.execute(
            postgres_query,
            SG_TYPE_ATTRIB,  # name
            len(all_attributes) + 2,  # Add Attributes at the end of the list
            ["project", "folder", "task"],  # scope
            {
                "type": "string",
                "title": "Shotgrid Type",
                "decription": "The Type of the Shotgrid entity.",
                "inherit": "False"
            }
        )

        return True

