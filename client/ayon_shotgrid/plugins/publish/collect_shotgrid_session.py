import os

from openpype.pipeline import KnownPublishError
import pyblish.api


class CollectShotgridSession(pyblish.api.ContextPlugin):
    """Collect shotgrid session using user credentials"""

    order = pyblish.api.CollectorOrder
    label = "Collecting Shotgrid session."

    def process(self, context):
        user_login = os.getenv("AYON_SG_USERNAME")
        if not user_login:
            raise KnownPublishError(
                "Have you logged in into Ayon Tray > Shotgrid ?"
            )

        self.log.info(
            "Attempting to create the Shotgrid Session for user: {0}".format(
                user_login
            )
        )

        shotgrid_module = context.data["openPypeModules"]["shotgrid"]
        shotgrid_url = shotgrid_module.get_sg_url()

        try:
            sg_session = shotgrid_module.get_shotgrid_session(user_login)
            self.log.info("Succesfully logged in into the Shotgrid API.")
        except Exception:
            raise KnownPublishError(
                "Could not connect to Shotgrid {} with user {}".format(
                    shotgrid_url,
                    user_login
                )
            )

        context.data["shotgridSession"] = sg_session
        context.data["shotgridUser"] = user_login

