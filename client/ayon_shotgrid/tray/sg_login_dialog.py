import os

from ayon_shotgrid.lib import credentials

from ayon_core import style
from ayon_core import resources
from qtpy import QtCore, QtWidgets, QtGui


class SgLoginDialog(QtWidgets.QDialog):
    """A QDialog that allows the person to set a Shotgrid Username.

    It also allows them to test the username against the API.
    """

    dialog_closed = QtCore.Signal()

    def __init__(self, addon, parent=None):
        super(SgLoginDialog, self).__init__(parent)
        self.addon = addon
        self.login_type = self.addon.get_client_login_type()

        self.setWindowTitle("AYON - Shotgrid Login")
        icon = QtGui.QIcon(resources.get_ayon_icon_filepath())
        self.setWindowIcon(icon)

        self.setWindowFlags(
            QtCore.Qt.WindowCloseButtonHint
            | QtCore.Qt.WindowMinimizeButtonHint
        )

        self.setStyleSheet(style.load_stylesheet())
        self.setContentsMargins(2, 2, 2, 2)

        self.setup_ui()

    def closeEvent(self, event):
        """Clear any message when closing the dialog."""
        self.sg_connection_message.setText("")
        self.dialog_closed.emit()
        super(SgLoginDialog, self).closeEvent(event)

    def setup_ui(self):
        server_url = self.addon.get_sg_url()

        if not server_url:
            server_url = "No Shotgrid Server set in AYON Settings."

        sg_server_url_label = QtWidgets.QLabel(
            "Please provide the credentials to log in into the "
            f"Shotgrid Server:\n{server_url}"
        )

        dialog_layout = QtWidgets.QVBoxLayout()
        dialog_layout.addWidget(sg_server_url_label)

        sg_username, sg_password = credentials.get_local_login()

        self.sg_username_input = QtWidgets.QLineEdit()

        if sg_username:
            self.sg_username_input.setText(sg_username)
        else:
            self.sg_username_input.setPlaceholderText("jane.doe@mycompany.com")
        self.sg_password_input = QtWidgets.QLineEdit()
        self.sg_password_input.setEchoMode(QtWidgets.QLineEdit.Password)

        if sg_password:
            self.sg_password_input.setText(sg_password)
        else:
            self.sg_password_input.setPlaceholderText("password1234")

        dialog_layout.addWidget(QtWidgets.QLabel("Shotgrid Username:"))
        dialog_layout.addWidget(self.sg_username_input)

        if self.login_type == "tray_pass":
            dialog_layout.addWidget(QtWidgets.QLabel("Shotgrid Password:"))
            dialog_layout.addWidget(self.sg_password_input)

        self.sg_check_login_button = QtWidgets.QPushButton(
            "Login into Shotgrid...")
        self.sg_check_login_button.clicked.connect(self.check_sg_credentials)
        self.sg_connection_message = QtWidgets.QLabel("")

        dialog_layout.addWidget(self.sg_check_login_button)
        dialog_layout.addWidget(self.sg_connection_message)

        self.setLayout(dialog_layout)

    def set_local_login(self):
        """Change Username label, save in local registry and set env var."""
        sg_username = self.sg_username_input.text()
        sg_password = self.sg_password_input.text()

        if self.login_type == "tray_pass":
            if sg_username and sg_password:
                credentials.save_local_login(sg_username, sg_password)
                os.environ["AYON_SG_USERNAME"] = sg_username
            else:
                credentials.clear_local_login()
                os.environ["AYON_SG_USERNAME"] = ""

        elif self.login_type == "tray_api_key":
            if sg_username:
                credentials.save_local_login(sg_username, None)
                os.environ["AYON_SG_USERNAME"] = sg_username
            else:
                credentials.clear_local_login()
                os.environ["AYON_SG_USERNAME"] = ""

    def check_sg_credentials(self):
        """Check if the provided username can login via the API."""
        sg_username = self.sg_username_input.text()
        sg_password = self.sg_password_input.text()

        kwargs = {
            "shotgrid_url": self.addon.get_sg_url(),
        }

        if self.login_type == "tray_pass":
            if not sg_username or not sg_password:
                self.sg_connection_message.setText(
                    "Please provide a valid username and password."
                )
                return
            kwargs.update({
                "username": sg_username,
                "password": sg_password
            })

        elif self.login_type == "tray_api_key":
            if not sg_username:
                self.sg_connection_message.setText(
                    "Please provide a valid username."
                )
                return
            kwargs.update({
                "username": sg_username,
                "api_key": self.addon.get_sg_api_key(),
                "script_name": self.addon.get_sg_script_name(),
            })

        login_result, login_message = credentials.check_user_permissions(
            **kwargs)

        self.set_local_login()

        if login_result:
            self.close()
        else:
            self.sg_connection_message.setText(login_message)
