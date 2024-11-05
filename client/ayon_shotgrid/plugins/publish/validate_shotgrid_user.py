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

        self.log.info("Login ShotGrid set in AYON is {}".format(user_login))
        self.log.info("Current ShotGrid Project is {}".format(sg_project))

        sg_user = sg_session.find_one(
            "HumanUser",
            [["login", "is", user_login]],
            ["projects", "permission_rule_set"],
        )

        sg_user_has_permission = False

        if sg_user:
            sg_user_has_permission = sg_user["permission_rule_set"]["name"] == "Admin"

        # It's not an admin, but it might still have permissions
        if not sg_user_has_permission:
            for project in sg_user["projects"]:
                if project["name"] == project_name:
                    sg_user_has_permission = True
                    break

        if not sg_user_has_permission:
            raise PublishValidationError(
                "Login {0} doesn't have access to the project {1} <{2}>".format(
                    user_login, project_name, sg_project
                )
            )

        self.log.info(
            "Login {0} has access to the project {1} <{2}>".format(
                user_login, project_name, sg_project
            )
        )
