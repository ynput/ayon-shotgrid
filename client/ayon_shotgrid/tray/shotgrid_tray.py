import os

from qtpy import QtWidgets

from ayon_shotgrid.lib import credentials
from ayon_shotgrid.tray.sg_login_dialog import SgLoginDialog


class ShotgridTrayWrapper:
    """ Shotgrid menu entry for the AYON tray.

    Displays the Shotgrid URL specified in the Server Addon Settings and
    allows the person to set a username to be used with the API.

    There's the option to check if said user has permissions to connect to the
    API.
    """
    def __init__(self, addon):
        self.addon = addon

        server_url = self.addon.get_sg_url()

        if not server_url:
            server_url = "No Shotgrid Server set in AYON Settings."

        self.sg_server_label = QtWidgets.QAction("Server: {0}".format(
                server_url
            )
        )
        self.sg_server_label.setDisabled(True)
        self.sg_username_label = QtWidgets.QAction("")
        self.sg_username_label.triggered.connect(self.show_sg_username_dialog)

        self.sg_username_dialog = SgLoginDialog(self.addon)
        self.sg_username_dialog.dialog_closed.connect(self.set_username_label)

    def show_sg_username_dialog(self):
        """Display the Shotgrid Username dialog

        Used to set a Shotgrid Username, that will then be used by any API call
        and to check that the user can access the Shotgrid API.
        """
        self.sg_username_dialog.show()
        self.sg_username_dialog.activateWindow()
        self.sg_username_dialog.raise_()

    def tray_menu(self, tray_menu):
        """Add Shotgrid Submenu to AYON tray.

        A non-actionable action displays the Shotgrid URL and the other
        action allows the person to set and check their Shotgrid username.

        Args:
            tray_menu (QtWidgets.QMenu): The AYON Tray menu.
        """
        shotgrid_tray_menu = QtWidgets.QMenu("Shotgrid", tray_menu)
        shotgrid_tray_menu.addAction(self.sg_server_label)
        shotgrid_tray_menu.addSeparator()
        shotgrid_tray_menu.addAction(self.sg_username_label)
        tray_menu.addMenu(shotgrid_tray_menu)

    def set_username_label(self):
        """Set the Username Label based on local login setting.

        Depending on the login credentials we want to display one message or
        another in the Shotgrid submenu action.
        """
        sg_username, _ = credentials.get_local_login()

        if sg_username:
            self.sg_username_label.setText(
                "Username: {} (Click to change)".format(sg_username)
            )
            os.environ["AYON_SG_USERNAME"] = sg_username
        else:
            self.sg_username_label.setText("Specify a Username...")
            os.environ["AYON_SG_USERNAME"] = ""
            self.show_sg_username_dialog()
