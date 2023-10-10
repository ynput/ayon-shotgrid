import os

from openpype.pipeline import KnownPublishError
import pyblish.api


class CollectShotgridSession(pyblish.api.ContextPlugin):
    """Collect shotgrid session using user credentials"""

    order = pyblish.api.CollectorOrder
    label = "Collecting Shotgrid session"

    def process(self, context):
        user_login = os.getenv("AYON_SG_USERNAME")
        if not user_login:
            raise KnownPublishError(
                "Have you logged in into Ayon Tray > Shotgrid?"
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
                "Could not connect to Shotgrid {0} with user {1}.".format(
                shotgrid_url,
                user_login
                )
            )

        if sg_session is None:
            raise KnownPublishError(
                "Could not connect to Shotgrid {0} with user {1}.".format(
                shotgrid_url,
                user_login
                )
            )

        context.data["shotgridSession"] = sg_session
        context.data["shotgridUser"] = user_login

