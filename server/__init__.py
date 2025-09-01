from typing import Any, Type, Optional
from nxtools import logging
from fastapi import Path, Body, Response

from ayon_server.api.dependencies import (
    CurrentUser,
    ProjectName,
)

from ayon_server.addons import BaseServerAddon
from ayon_server.lib.postgres import Postgres
from ayon_server.events import dispatch_event

from .settings import ShotgridSettings

SG_ID_ATTRIB = "shotgridId"
SG_TYPE_ATTRIB = "shotgridType"
SG_PUSH_ATTRIB = "shotgridPush"


class ShotgridAddon(BaseServerAddon):
    settings_model: Type[ShotgridSettings] = ShotgridSettings

    frontend_scopes: dict[str, Any] = {"settings": {}}

    def initialize(self) -> None:

        # returning user for SG id value
        self.add_endpoint(
            "/get_ayon_name_by_sg_id/{sg_user_id}",
            self.get_ayon_name_by_sg_id,
            method="GET",
        )
        self.add_endpoint(
            "/{project_name}/trigger_mediapath",
            self.trigger_mediapath_event,
            method="POST",
        )

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
            "SELECT name, scope from public.attributes "
            f"WHERE (name = '{SG_ID_ATTRIB}'"
            f" OR name = '{SG_TYPE_ATTRIB}'"
            f" OR name = '{SG_PUSH_ATTRIB}') "
        )

        expected_scopes = {
            SG_ID_ATTRIB: ["project", "folder", "task", "version"],
            SG_TYPE_ATTRIB:  ["project", "folder", "task", "version"],
            SG_PUSH_ATTRIB: ["project"]
        }
        not_matching_scopes = False
        for attr in shotgrid_attributes:
            if expected_scopes[attr["name"]] != attr["scope"]:
                not_matching_scopes = True
                break
        if (not shotgrid_attributes or
                len(shotgrid_attributes) < 3 or
                not_matching_scopes):
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
                expected_scopes[SG_ID_ATTRIB],  # scope
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
                expected_scopes[SG_TYPE_ATTRIB],  # scope
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
                expected_scopes[SG_PUSH_ATTRIB],  # scope
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

    async def get_ayon_name_by_sg_id(
        self,
        sg_user_id: str = Path(
            ...,
            description="Id of Shotgrid user ",
            example="123",
        )
    ) -> Optional[str]:
        """Queries user for specific 'sg_user_id' field in 'data'.

        Field added during user synchronization to be explicit, not depending that
        SG login will be same as AYON (which is not as @ is not allowed in AYON)
        """
        query = f"""
            SELECT
                *
            FROM public.users
            WHERE data ? 'sg_user_id' AND data->>'sg_user_id' = '{sg_user_id}';
        """

        res = await Postgres.fetch(query)
        if res:
            return res[0]["name"]

    async def trigger_mediapath_event(
        self,
        user: CurrentUser,
        project_name: ProjectName,
        data: dict[str, Any] = Body(...),
    ) -> Response:
        """Temporary endpoint to trigger event with explicit sender_type"""
        response = await dispatch_event(
            "flow.version.mediapath",
            project=project_name,
            sender_type="publish",
            description="Update media paths on synchronized Version",
            summary=data,
        )

        return Response(status_code=200, content=str(response))
