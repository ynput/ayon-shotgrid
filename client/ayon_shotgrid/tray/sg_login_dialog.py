import os

from ayon_shotgrid.lib import credentials

import ayon_api
from openpype import style
from openpype import resources
from qtpy import QtCore, QtWidgets, QtGui

class SgLoginDialog(QtWidgets.QDialog):
    """A QDialog that allows the person to set a Shotgrid Username.

    It also allows them to test the username agains the API.
    """

    dialog_closed = QtCore.Signal()

    def __init__(self, module, parent=None):
        super(SgLoginDialog, self).__init__(parent)
        self.module = module

        self.setWindowTitle("Ayon - Shotgrid Login")
        icon = QtGui.QIcon(resources.get_openpype_icon_filepath())
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
        server_url = self.module.get_sg_url()

        if not server_url:
            server_url = "No Shotgrid Server set in Ayon Settings."
        
        sg_server_url_label = QtWidgets.QLabel(
            "Please provide the credentials to log in into the Shotgrid Server:\n{}".format(server_url)
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
            self.sg_password_input.setPlaceholderText("c0mPre$Hi0n")

        dialog_layout.addWidget(QtWidgets.QLabel("Shotgrid Username:"))
        dialog_layout.addWidget(self.sg_username_input)

        dialog_layout.addWidget(QtWidgets.QLabel("Shotgrid Password:"))
        dialog_layout.addWidget(self.sg_password_input)

        self.sg_check_login_button = QtWidgets.QPushButton("Login into Shotgrid...")
        self.sg_check_login_button.clicked.connect(self.check_sg_credentials)
        self.sg_connection_message = QtWidgets.QLabel("")

        dialog_layout.addWidget(self.sg_check_login_button)
        dialog_layout.addWidget(self.sg_connection_message)

        self.setLayout(dialog_layout)

    def set_local_login(self):
        """Change Username label, save in local registry and set env var."""
        sg_username = self.sg_username_input.text()
        sg_password = self.sg_password_input.text()

        if sg_username and sg_password:
            credentials.save_local_login(sg_username, sg_password)
            os.environ["AYON_SG_USERNAME"] = sg_username
        else:
            credentials.clear_local_login()
            os.environ["AYON_SG_USERNAME"] = ""

    def check_sg_credentials(self):
        """Check if the provided username can login via the API."""
        sg_username = self.sg_username_input.text()
        sg_password = self.sg_password_input.text()

        login_result, login_message = credentials.check_user_permissions(
            self.module.get_sg_url(),
            sg_username,
            sg_password,
        )

        self.set_local_login()

        if login_result:
            self.close()
        else:
            self.sg_connection_message.setText(login_message)
