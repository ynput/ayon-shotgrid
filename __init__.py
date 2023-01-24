from typing import Type

from ayon_server.addons import BaseServerAddon
from ayon_server.lib.postgres import Postgres

from .settings import MySettings, DEFAULT_VALUES
from .version import __version__


SG_ID_ATTRIB = "shotgridId"
SG_PATH_ATTRIB = "shotgridPath"


class ShotgridAddon(BaseServerAddon):
    name = "shotgrid"
    title = "Shotgrid"
    version = __version__
    settings_model: Type[MySettings] = MySettings

    async def get_default_settings(self):
        settings_model_cls = self.get_settings_model()
        return settings_model_cls(**DEFAULT_VALUES)

    async def setup(self):
        need_restart = await self.create_shotgrid_attributes()
        if need_restart:
            self.request_server_restart()

    async def create_shotgrid_attributes(self) -> bool:
        """Make sure there are required attributes which ftrack addon needs.

        Returns:
            bool: 'True' if an attribute was created or updated.
        """

        expected_scope = ["project", "folder", "task"]

        query = (
            "SELECT name, position, scope, data from public.attributes "
            "WHERE (name = '{SG_ID_ATTRIB}' OR name = '{SG_PATH_ATTRIB}') "
            "AND (scope = '{set(expected_scope)}')"
        )
        shotgrid_id_attribute_data = {
            "type": "string",
            "title": "Ftrack id"
        }
        shotgrid_path_attribute_data = {
            "type": "string",
            "title": "Ftrack path"
        }

        ftrack_id_match_position = None
        ftrack_id_matches = False
        ftrack_path_match_position = None
        ftrack_path_matches = False

        if Postgres.pool is None:
            await Postgres.connect()

        async for position, row in enumerate(Postgres.iterate(query), start=1):
            if row["name"] == SG_ID_ATTRIB:
                # Check if scope is matching ftrack addon requirements
                if set(row["scope"]) == set(expected_scope):
                    ftrack_id_matches = True
                ftrack_id_match_position = row["position"]

            elif row["name"] == SG_PATH_ATTRIB:
                if set(row["scope"]) == set(expected_scope):
                    ftrack_path_matches = True
                ftrack_path_match_position = row["position"]

        if ftrack_id_matches and ftrack_path_matches:
            return False

        postgre_query = "\n".join((
            "INSERT INTO public.attributes",
            "    (name, position, scope, data)",
            "VALUES",
            "    ($1, $2, $3, $4)",
            "ON CONFLICT (name)",
            "DO UPDATE SET",
            "    scope = $3,",
            "    data = $4",
        ))
        if not ftrack_id_matches:
            # Reuse position from found attribute
            if ftrack_id_match_position is None:
                ftrack_id_match_position = position
                position += 1

            await Postgres.execute(
                postgre_query,
                SG_ID_ATTRIB,
                ftrack_id_match_position,
                expected_scope,
                shotgrid_id_attribute_data,
            )

        if not ftrack_path_matches:
            if ftrack_path_match_position is None:
                ftrack_path_match_position = position
                position += 1

            await Postgres.execute(
                postgre_query,
                SG_PATH_ATTRIB,
                ftrack_path_match_position,
                expected_scope,
                shotgrid_path_attribute_data,
            )
        return True

