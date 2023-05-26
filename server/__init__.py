import json
import socket
from typing import Any, Type

from ayon_server.addons import BaseServerAddon
from ayon_server.api.dependencies import dep_current_user, dep_project_name
from ayon_server.entities import UserEntity
from ayon_server.events import dispatch_event
from ayon_server.lib.postgres import Postgres
from .settings import ShotgridSettings, DEFAULT_VALUES
from .version import __version__

from fastapi import Depends
import requests
from starlette.requests import Request
from nxtools import logging


SG_ID_ATTRIB = "shotgridId"
SG_TYPE_ATTRIB = "shotgridType"


class ShotgridAddon(BaseServerAddon):
    name = "shotgrid"
    title = "Shotgrid Sync"
    version = __version__
    settings_model: Type[ShotgridSettings] = ShotgridSettings

    frontend_scopes: dict[str, Any] = {"settings": {}}

    def initialize(self):
        logging.info("Initializing Shotgrid Addon.")

        self.add_endpoint(
            "create-project",
            self._create_project,
            method="POST",
            name="create-shotgrid-project",
            description="Create project in Ayon, with the given name.",
        )
        logging.info("Added Create Project Endpoint.")

        self.add_endpoint(
            "sync-from-shotgrid/{project_name}",
            self._sync_from_shotgrid,
            method="GET",
            name="sync-from-shotgrid",
            description="Trigger Shotgrid -> Ayon Sync of entities.",
        )
        logging.info("Added Sync from Shotgrid Project Endpoint.")

        self.add_endpoint(
            "get-importable-projects",
            self._get_importable_projects,
            method="GET",
            name="get-importable-projects",
            description="Return a list of Shotgrid projects ready to be imported into Ayon.",
        )
        logging.info("Added Get Syncable Projects Endpoint.")

    async def _dispatch_shotgrid_event(
        self,
        action,
        user_name,
        project_name,
        description=None
    ):
        event_id = await dispatch_event(
            "shotgrid.event",
            sender=socket.gethostname(),
            project=project_name,
            user=user_name,
            description=description,
            summary=None,
            payload={
                "action": action,
                "user_name": user_name,
                "project_name": project_name,
            },
        )
        logging.info(f"Dispatched event {event_id}")
        return event_id

    async def _sync_from_shotgrid(
        self,
        user: UserEntity = Depends(dep_current_user),
        project_name: str = Depends(dep_project_name),
    ):
        await self._dispatch_shotgrid_event(
            "sync-from-shotgrid",
            user.name,
            project_name,
            description=f"Sync project '{project_name}' from Shotgrid."
        )

    async def _create_project(
        self,
        request: Request,
        user: UserEntity = Depends(dep_current_user)
    ):
        request_body = await request.body()

        if not request_body:
            logging.error(f"Request has no body: {request_body}")
            return
        else:
            request_body = json.loads(request_body)

        project_name = request_body.get("project_name")
        project_code = request_body.get("project_code")

        logging.info("Project name is: ", project_name)
        description = f"Create {project_name} from Shotgrid."

        if project_name and project_code:
            event_id = await dispatch_event(
                "shotgrid.event",
                sender=socket.gethostname(),
                project=project_name,
                user=user.name,
                description=description,
                summary=None,
                payload={
                    "action": "create-project",
                    "user_name": user.name,
                    "project_name": project_name,
                    "project_code": project_code,
                    "description": description,
                },
            )
            logging.info(f"Dispatched event {event_id}")

    async def _get_importable_projects(self):
        """ Query Shotgrid for existing non-template Projects.

        It uses the Rest APi to avoid importing the Shotgrid API.
        """
        logging.info("Trying to fetch projects from Shotgrid.")
        addon_settings = await self.get_studio_settings()

        if not addon_settings:
            logging.error(f"Unable to get Studio Settings: {self.name} addon.")
            return
        elif not all((
            addon_settings.shotgrid_server,
            addon_settings.shotgrid_script_name,
            addon_settings.shotgrid_api_key,
            addon_settings.shotgrid_project_code_field
        )):
            logging.error("Missing data in the addon settings.")
            return

        shotgrid_url = addon_settings.shotgrid_server
        if shotgrid_url.endswith("/"):
            shotgrid_url = shotgrid_url.rstrip("/")

        shotgrid_credentials_token = requests.post(
            f"{addon_settings.shotgrid_server}/api/v1/auth/access_token",
            data={
                "client_id": f"{addon_settings.shotgrid_script_name}",
                "client_secret": f"{addon_settings.shotgrid_api_key}",
                "grant_type": "client_credentials"
            }
        )
        shotgrid_token = shotgrid_credentials_token.json().get('access_token')

        if not shotgrid_token:
            logging.error("Unable to Acquire Shotgrid REST API token.")
            return

        logging.info("Querying the Shotgrid REST API token.")
        request_headers = {
            "Authorization": f"Bearer {shotgrid_token}",
            "Accept": "application/vnd+shotgun.api3_array+json"
        }

        shotgrid_projects = requests.get(
            f"{shotgrid_url}/api/v1/entity/projects/",
            headers=request_headers
        )

        sg_projects = []

        if shotgrid_projects.json().get("data"):
            logging.info("Shotgrid REST API returned some data, processing it.")
            for project in shotgrid_projects.json().get("data"):
                sg_project = requests.get(
                    f"{shotgrid_url}/api/v1/entity/projects/{project['id']}",
                    data=json.dumps({
                        "fields": [
                            "name",
                            addon_settings.shotgrid_project_code_field,
                            "sg_ayon_sync_status",
                        ]
                    }),
                    headers=request_headers
                )
                if not sg_project.json()["data"]:
                    continue

                sg_project = sg_project.json()["data"]

                if sg_project["attributes"].get("is_template"):
                    continue

                sg_projects.append({
                    "projectName": sg_project["attributes"].get("name"),
                    "projectCode": sg_project["attributes"].get(
                        addon_settings.shotgrid_project_code_field
                    ),
                    "shotgridId": sg_project["id"],
                    "ayonId": sg_project["attributes"].get("sg_ayon_id"),
                    "ayonAutoSync": sg_project["attributes"].get("sg_ayon_auto_sync"),
                })
        logging.info("Finished processing Shotgrid data.")
        logging.debug(f"Processed the following projects {sg_projects}.")
        return sg_projects

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
                "description": "The ID in the Shotgrid Instance."
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
                "decription": "The Type of the Shotgrid entity."
            }
        )

        return True

