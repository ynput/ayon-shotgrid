import os

import pyblish.api

from ayon_core.pipeline import KnownPublishError


class CollectShotgridSession(pyblish.api.ContextPlugin):
    """Collect shotgrid session using user credentials"""

    order = pyblish.api.CollectorOrder
    label = "Collecting Shotgrid session"

    def process(self, context):
        user_login = (
            os.getenv("AYON_SG_USERNAME")
            # TODO: Remove USER env variable in future once ayon-core deadline
            # passing of AYON_SG_USERNAME is solved
            or os.getenv("USER")
        )
        self.log.info(f"User login: {user_login}")
        if not user_login:
            raise KnownPublishError(
                "User not found in environment, make sure it's set."
            )

        shotgrid_addon = context.data["ayonAddons"]["shotgrid"]
        shotgrid_url = shotgrid_addon.get_sg_url()

        self.log.info(
            f"Creating Shotgrid Session for user: {user_login} "
            f"at {shotgrid_url}"
        )

        try:
            sg_session = shotgrid_addon.create_shotgrid_session()
            self.log.info("Succesfully logged in into the Shotgrid API.")
        except Exception as e:
            self.log.error("Failed to connect to Shotgrid.", exc_info=True)
            raise KnownPublishError(
                f"Could not connect to Shotgrid {shotgrid_url} "
                f"with user {user_login}."
            ) from e

        if sg_session is None:
            raise KnownPublishError(
                f"Could not connect to Shotgrid {shotgrid_url} "
                f"with user {user_login}."
            )

        context.data["shotgridSession"] = sg_session
        context.data["shotgridUser"] = user_login

        local_storage_enabled = shotgrid_addon.is_local_storage_enabled()
        context.data["shotgridLocalStorageEnabled"] = local_storage_enabled
        self.log.info(
            f"Shotgrid local storage enabled: {local_storage_enabled}")
        if local_storage_enabled:
            local_storage_key = shotgrid_addon.get_local_storage_key()
            self.log.info(f"Using local storage entry {local_storage_key}")
            context.data["shotgridLocalStorageKey"] = local_storage_key
