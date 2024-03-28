import os

from openpype.pipeline import KnownPublishError
import pyblish.api


class CollectShotgridSession(pyblish.api.ContextPlugin):
    """Collect shotgrid session using user credentials"""

    order = pyblish.api.CollectorOrder
    label = "Collecting Shotgrid session"

    def process(self, context):
        user_login = os.getenv("USER") or os.getenv("AYON_SG_USER")
        if not user_login:
            raise KnownPublishError(
                "User not found in environment, make sure it's set."
            )

        shotgrid_module = context.data["openPypeModules"]["shotgrid"]
        shotgrid_url = shotgrid_module.get_sg_url()

        self.log.info(
            "Creating Shotgrid Session for user: {0} at {1}".format(
                user_login, shotgrid_url
            )
        )

        try:
            sg_session = shotgrid_module.create_shotgrid_session()
            self.log.info("Succesfully logged in into the Shotgrid API.")
        except Exception as e:
            self.log.error("Failed to connect to Shotgrid.", exc_info=True)
            raise KnownPublishError(
                f"Could not connect to Shotgrid {shotgrid_url} "
                f"with user {user_login}."
            ) from e

        if sg_session is None:
            raise KnownPublishError(
                "Could not connect to Shotgrid {0} with user {1}.".format(
                shotgrid_url,
                user_login
                )
            )

        context.data["shotgridSession"] = sg_session
        context.data["shotgridUser"] = user_login

        local_storage_enabled = shotgrid_module.is_local_storage_enabled()
        context.data["shotgridLocalStorageEnabled"] = local_storage_enabled
        self.log.info(f"Shotgrid local storage enabled: {local_storage_enabled}")
        if local_storage_enabled:
            local_storage_key = shotgrid_module.get_local_storage_key()
            self.log.info(f"Using local storage entry {local_storage_key}")
            context.data["shotgridLocalStorageKey"] = local_storage_key
        