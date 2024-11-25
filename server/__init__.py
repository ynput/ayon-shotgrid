from typing import Any, Type

from ayon_server.addons import BaseServerAddon
from ayon_server.lib.postgres import Postgres
from .settings import ShotgridSettings
from nxtools import logging


SG_ID_ATTRIB = "shotgridId"
SG_TYPE_ATTRIB = "shotgridType"
SG_PUSH_ATTRIB = "shotgridPush"


class ShotgridAddon(BaseServerAddon):
    settings_model: Type[ShotgridSettings] = ShotgridSettings

    frontend_scopes: dict[str, Any] = {"settings": {}}

    async def setup(self):
        need_restart = await self.create_shotgrid_attributes()
        if need_restart:
            logging.debug(
                "Created or updated attributes in database, "
                "requesting a server restart."
            )
            self.request_server_restart()

    async def create_shotgrid_attributes(self) -> bool:
        """Make sure AYON has the `shotgridId` and `shotgridPath` attributes.

        Returns:
            bool: 'True' if an attribute was created or updated.
        """

        if Postgres.pool is None:
            await Postgres.connect()

        all_attributes = await Postgres.fetch(
            "SELECT name from public.attributes"
        )

        num_of_attributes = len(all_attributes)

        shotgrid_attributes = await Postgres.fetch(
            "SELECT name from public.attributes "
            f"WHERE (name = '{SG_ID_ATTRIB}'"
            f" OR name = '{SG_TYPE_ATTRIB}'"
            f" OR name = '{SG_PUSH_ATTRIB}') "
        )

        if not shotgrid_attributes or len(shotgrid_attributes) < 3:
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
                num_of_attributes + 1,  # Add Attributes at the end of the list
                ["project", "folder", "task"],  # scope
                {
                    "type": "string",
                    "title": "Shotgrid ID",
                    "description": "The Shotgrid ID of this entity.",
                    "inherit": False
                }
            )

            await Postgres.execute(
                postgres_query,
                SG_TYPE_ATTRIB,  # name
                num_of_attributes + 2,  # Add Attributes at the end of the list
                ["project", "folder", "task"],  # scope
                {
                    "type": "string",
                    "title": "Shotgrid Type",
                    "description": "The Shotgrid Type of this entity.",
                    "inherit": False
                }
            )

            await Postgres.execute(
                postgres_query,
                SG_PUSH_ATTRIB,  # name
                num_of_attributes + 3,  # Add Attributes at the end of the list
                ["project"],  # scope
                {
                    "type": "boolean",
                    "title": "Shotgrid Push",
                    "description": (
                        "Push changes done to this project to ShotGrid. "
                        "Requires the transmitter service."
                    ),
                    "inherit": False,
                    "value": False,
                }
            )

            return True

        else:
            logging.debug("Shotgrid Attributes already exist.")
            return False
