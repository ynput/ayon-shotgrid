import socket
from typing import Any, Type
from urllib.parse import parse_qs

from ayon_server.addons import BaseServerAddon
from ayon_server.api.dependencies import dep_current_user, dep_project_name
from ayon_server.entities import UserEntity
from ayon_server.events import dispatch_event
from ayon_server.lib.postgres import Postgres
from .settings import ShotgridSettings, DEFAULT_VALUES
from .version import __version__

from fastapi import Body, Depends
from starlette.requests import Request
from nxtools import logging


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
        logging.info("Added Create Attributes Endpoint.")
        self.add_endpoint(
            "create-project",
            self._create_project,
            method="POST",
            name="prepare-shotgrid-project",
            description="Find project in Shotgrid, and create all the needed attributes.",
        )
        self.add_endpoint(
            "prepare-shotgrid-project/{project_name}",
            self._prepare_project,
            method="GET",
            name="prepare-shotgrid-project",
            description="Find project in Shotgrid, and create all the needed attributes.",
        )
        self.add_endpoint(
            "sync-from-shotgrid/{project_name}",
            self._sync_from_shotgrid,
            method="GET",
            name="sync-from-shotgrid",
            description="Trigger Shotgrid -> Ayon Sync with this endpoint.",
        )

    async def _prepare_project(
        self,
        user: UserEntity = Depends(dep_current_user),
        project_name: str = Depends(dep_project_name),
    ):
        """ Dispatch an event into Ayon evetn's system.

        If there's any processor listening for `shotgird.endpoint` it
        will handle the event.
        """
        user_name = user.name
        event_id = await dispatch_event(
            "shotgrid.event",
            sender=socket.gethostname(),
            project=project_name,
            user=user_name,
            description=f"Prepare Project {project_name} in Shotgrid.",
            summary=None,
            payload={
                "action": "prepare-project",
                "username": user_name,
                "project": project_name,
            },
        )
        logging.info(f"Dispatched event {event_id}")

    async def _sync_from_shotgrid(
        self,
        user: UserEntity = Depends(dep_current_user),
        project_name: str = Depends(dep_project_name),
    ):
        user_name = user.name
        event_id = await dispatch_event(
            "shotgrid.event",
            sender=socket.gethostname(),
            project=project_name,
            user=user_name,
            description=f"Sync project '{project_name}' from Shotgrid.",
            payload={
                "action": "sync-from-shotgrid",
                "username": user_name,
                "project": project_name,
            },
        )
        logging.info(f"Dispatched event {event_id}")

    async def _create_project(self, request: Request):
        request_body = await request.body()
        if not request_body:
            print("Request has no body")
            print(f"{request_body}")
            return

        query_data = parse_qs(request_body)
        print(query_data)

        project_name = next(iter(query_data.get('project_name', [])), "")
        user_name = next(query_data.get('user_login', []), "").split("@")[0]

        if project_name:
            event_id = await dispatch_event(
                "shotgrid.event",
                sender=socket.gethostname(),
                project="project_name",
                user="",
                description=f"Create {project_name} from Shotgrid.",
                payload={
                    "action": "create-project",
                    "project":  project_name,
                    "username": user_name
                },
            )
            logging.info(f"Dispatched event {event_id}")

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
            f"WHERE (name = '{SG_ID_ATTRIB}' OR name = '{SG_PATH_ATTRIB}') "
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

