import os

from ayon_shotgrid.lib import credentials

import ayon_api
from openpype import style
from openpype import resources
from qtpy import QtCore, QtWidgets, QtGui

class ChangeSgUsername(QtWidgets.QDialog):
    """A QDialog that allows the person to set a Shotgrid Username.

    It also allows them to test the username agains the API.
    """

    dialog_closed = QtCore.Signal()

    def __init__(self, module, parent=None):
        super(ChangeSgUsername, self).__init__(parent)
        self.module = module

        self.setWindowTitle("Ayon - Shotgrid Username")
        icon = QtGui.QIcon(resources.get_openpype_icon_filepath())
        self.setWindowIcon(icon)

        self.setWindowFlags(
            QtCore.Qt.WindowCloseButtonHint
            | QtCore.Qt.WindowMinimizeButtonHint
        )

        self.setStyleSheet(style.load_stylesheet())
        self.setContentsMargins(20, 10, 20, 10)

        self.setup_ui()

    def closeEvent(self, event):
        """Clear any message when closing the dialog."""
        self.sg_connection_message.setText("")
        self.dialog_closed.emit()
        super(ChangeSgUsername, self).closeEvent(event)

    def setup_ui(self):
        server_url = self.module.get_sg_url()

        if not server_url:
            server_url = "No Shotgrid Server set in Ayon Settings."

        sg_server_url_label = QtWidgets.QLabel(
            "Server:\n{}".format(server_url)
        )
        self.sg_username_label = QtWidgets.QLabel("Username:")

        dialog_layout = QtWidgets.QVBoxLayout()
        dialog_layout.addWidget(sg_server_url_label)
        dialog_layout.addWidget(self.sg_username_label)

        self.sg_username_input = QtWidgets.QLineEdit()
        self.sg_username_set_button = QtWidgets.QPushButton("Set")
        self.sg_username_set_button.clicked.connect(self.set_local_login)

        sg_username = credentials.get_local_login()

        if sg_username:
            self.sg_username_input.setText(sg_username)
        else:
            self.sg_username_input.setPlaceholderText("jane.doe@mycompany.com")

        username_layout = QtWidgets.QHBoxLayout()
        username_layout.setContentsMargins(0, 0, 0, 20)
        username_layout.addWidget(self.sg_username_input)
        username_layout.addWidget(self.sg_username_set_button)

        dialog_layout.addLayout(username_layout)

        self.sg_check_login_label= QtWidgets.QLabel((
            "Use the button below to check if the provided\n"
            "user has access to the Shotgird API.")
        )
        self.sg_check_login_button = QtWidgets.QPushButton("Check Shotgrid Login")
        self.sg_check_login_button.clicked.connect(self.check_sg_credentials)
        self.sg_connection_message = QtWidgets.QLabel("")

        dialog_layout.addWidget(self.sg_check_login_label)
        dialog_layout.addWidget(self.sg_check_login_button)
        dialog_layout.addWidget(self.sg_connection_message)


        self.setLayout(dialog_layout)

    def set_local_login(self):
        """Change Username label, save in local registry and set env var."""
        sg_username = self.sg_username_input.text()
        
        if sg_username:
            credentials.save_local_login(sg_username)
            os.environ["AYON_SG_USERNAME"] = sg_username
        else:
            credentials.clear_local_login()
            os.environ["AYON_SG_USERNAME"] = ""

    def check_sg_credentials(self):
        """Check if the provided username can login via the API."""
        sg_username = self.sg_username_input.text()
        login_result, login_message = credentials.check_user_permissions(
            self.module.get_sg_url(),
            self.module._shotgrid_script_name,
            self.module._shotgrid_api_key,
            sg_username,
        )

        self.set_local_login()
        self.sg_connection_message.setText(login_message)
