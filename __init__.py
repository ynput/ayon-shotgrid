from typing import Type

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

        expected_scope = ["project", "folder", "task"]

        query = (
            "SELECT name, position, scope, data from public.attributes "
            f"WHERE (name = '{SG_ID_ATTRIB}' OR name = '{SG_PATH_ATTRIB}') "
            "AND (scope = '{project, folder, task}')"
        )

        # ftrack_id_match_position = None
        # ftrack_id_matches = False
        # ftrack_path_match_position = None
        # ftrack_path_matches = False

        if Postgres.pool is None:
            await Postgres.connect()

        shotgrid_attributes = await Postgres.fetch(query)
        # all_attributes = await Postgres.fetch("SELECT name, position, scope, data from public.attributes WHERE scope = '{project, folder, version, representation, task}'")
        # All attributes are: [<Record name='fullName' position=10 scope=['user'] data={'type': 'string', 'title': 'Full name', 'example': 'Jane Doe'}>, <Record name='email' position=11 scope=['user'] data={'type': 'string', 'title': 'E-Mail', 'example': 'jane.doe@ayon.cloud'}>, <Record name='avatarUrl' position=12 scope=['user'] data={'type': 'string', 'title': 'Avatar URL'}>, <Record name='subsetGroup' position=13 scope=['subset'] data={'type': 'string', 'title': 'Subset group'}>, <Record name='intent' position=14 scope=['version'] data={'type': 'string', 'title': 'Intent'}>, <Record name='source' position=15 scope=['version'] data={'type': 'string', 'title': 'Source'}>, <Record name='comment' position=16 scope=['version'] data={'type': 'string', 'title': 'Comment'}>, <Record name='site' position=17 scope=['version'] data={'type': 'string', 'title': 'Site', 'example': 'workstation42'}>, <Record name='families' position=18 scope=['version'] data={'type': 'list_of_strings', 'title': 'Families'}>, <Record name='colorSpace' position=19 scope=['version'] data={'type': 'string', 'title': 'Color space', 'example': 'rec709'}>, <Record name='fps' position=0 scope=['project', 'folder', 'version', 'representation', 'task'] data={'gt': 0, 'type': 'float', 'title': 'FPS', 'default': 25, 'example': 25, 'description': 'Frame rate'}>, <Record name='resolutionWidth' position=1 scope=['project', 'folder', 'version', 'representation', 'task'] data={'gt': 0, 'lt': 50000, 'type': 'integer', 'title': 'Width', 'default': 1920, 'example': 1920, 'description': 'Horizontal resolution'}>, <Record name='resolutionHeight' position=2 scope=['project', 'folder', 'version', 'representation', 'task'] data={'gt': 0, 'lt': 50000, 'type': 'integer', 'title': 'Height', 'default': 1080, 'example': 1080, 'description': 'Vertical resolution'}>, <Record name='pixelAspect' position=3 scope=['project', 'folder', 'version', 'representation', 'task'] data={'gt': 0, 'type': 'float', 'title': 'Pixel aspect', 'default': 1.0, 'example': 1.0}>, <Record name='clipIn' position=4 scope=['project', 'folder', 'version', 'representation', 'task'] data={'type': 'integer', 'title': 'Clip In', 'default': 1, 'example': 1}>, <Record name='clipOut' position=5 scope=['project', 'folder', 'version', 'representation', 'task'] data={'type': 'integer', 'title': 'Clip Out', 'default': 1, 'example': 1}>, <Record name='frameStart' position=6 scope=['project', 'folder', 'version', 'representation', 'task'] data={'type': 'integer', 'title': 'Start frame', 'default': 1001, 'example': 1001}>, <Record name='frameEnd' position=7 scope=['project', 'folder', 'version', 'representation', 'task'] data={'type': 'integer', 'title': 'End frame', 'default': 1001}>, <Record name='handleStart' position=8 scope=['project', 'folder', 'version', 'representation', 'task'] data={'type': 'integer', 'title': 'Handle start', 'default': 0}>, <Record name='handleEnd' position=9 scope=['project', 'folder', 'version', 'representation', 'task'] data={'type': 'integer', 'title': 'Handle end', 'default': 0}>, <Record name='path' position=20 scope=['representation'] data={'type': 'string', 'title': 'Path'}>, <Record name='template' position=21 scope=['representation'] data={'type': 'string', 'title': 'Template'}>, <Record name='extension' position=22 scope=['representation', 'workfile'] data={'type': 'string', 'title': 'File extension'}>, <Record name='testEnum' position=23 scope=['project', 'folder', 'version', 'representation', 'task'] data={'enum': [{'label': 'Test 1', 'value': 'test1'}, {'label': 'Test 2', 'value': 'test2'}, {'label': 'Test 3', 'value': 'test3'}], 'type': 'string', 'title': 'Test enum', 'default': 'test1', 'example': 'test1'}>, <Record name='testList' position=24 scope=['project', 'folder', 'version', 'representation', 'task'] data={'enum': [{'label': 'Test 1', 'value': 'test1'}, {'label': 'Test 2', 'value': 'test2'}, {'label': 'Test 3', 'value': 'test3'}], 'type': 'list_of_strings', 'title': 'Test LoS', 'default': ['test1'], 'example': ['test1', 'test2']}>]
        #logging.info(f"All attributes are: {all_attributes}")
        # for attr in all_attributes:
        #     logging.info(attr["scope"])
        #     logging.info(type(attr["scope"]))

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
            SG_ID_ATTRIB, # name
            0, # position
            ["project", "folder", "task"], #scope
            {
                "type": "string",
                "title": "Shotgrid ID",
                "description": "The ID in the Shotgrid Instance."
            }
        )

        await Postgres.execute(
            postgres_query,
            SG_PATH_ATTRIB, # name
            1, # position
            ["project", "folder", "task"], #scope
            {
                "type": "string",
                "title": "Shotgrid Path",
                "decription": "The path to the Asset from the Shotgrid Instance."
            }
        )

        return True

