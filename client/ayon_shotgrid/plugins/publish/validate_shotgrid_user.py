import pyblish.api

from ayon_core.pipeline.publish import ValidateContentsOrder
from ayon_core.pipeline import PublishValidationError


class ValidateShotgridUser(pyblish.api.ContextPlugin):
    """
    Check if user is valid and have access to the project.
    """
    label = "Validate Shotgrid User"
    order = ValidateContentsOrder

    def process(self, context):
        sg_session = context.data.get("shotgridSession")
        user_login = context.data.get("shotgridUser")
        sg_project = context.data.get("shotgridProject")
        project_name = context.data["projectEntity"]["name"]

        if not (user_login and sg_session and sg_project):
            raise PublishValidationError("Missing Shotgrid Credentials")

        self.log.info("Login Shotgrid set in Ayon is {}".format(user_login))
        self.log.info("Current shotgun Project is {}".format(sg_project))

        sg_user = sg_session.find_one(
            "HumanUser",
            [
                ["login", "is", user_login],
                ["projects", "name_contains", project_name]
            ],
            ["projects"]
        )

        self.log.info("Found User in Shotgrid: {}".format(sg_user))

        if not sg_user:
            raise PublishValidationError(
                "Login {0} don't have access to the project {1} <{2}>".format(
                    user_login, project_name, sg_project
                )
            )

        self.log.info(
            "Login {0} have access to the project {1} <{2}>".format(
                user_login, project_name, sg_project
            )
        )
