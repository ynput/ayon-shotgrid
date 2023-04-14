import shotgun_api3
from shotgun_api3.shotgun import AuthenticationFault

from openpype.lib import OpenPypeSettingsRegistry


def check_user_permissions(shotgrid_url, script_name, api_key, username):
    """Chek if the provided user can access the Shotgrid API.

    Args:
        shotgrid_url (str): The Shotgun server URL.
        script_name (str): The Shotgrid API script name.
        api_key (str): The Shotgrid API key.
        username (str): The Shotgrid username to use the Session as.
        
    Returns:
        tuple(bool, str): Whether the connection was succsefull or not, and a 
            string message with the result.
     """
    
    if not shotgrid_url or not script_name or not api_key or not username:
        return (False, "Missing a field.")

    try:
        session = create_sg_session(
            shotgrid_url,
            script_name,
            api_key,
            username
        )
        session.close()
    except AuthenticationFault as e:
        return (False, str(e))

    return (True, "Succesfully logged in.")


def clear_local_login():
    """Clear the Shotgrid Login entry from the local registry. """
    reg = OpenPypeSettingsRegistry()
    reg.delete_item("shotgrid_login")


def create_sg_session(shotgrid_url, script_name, api_key, username):
    """Attempt to create a Shotgun Session

    Args:
        shotgrid_url (str): The Shotgun server URL.
        script_name (str): The Shotgrid API script name.
        api_key (str): The Shotgrid API key.
        username (str): The Shotgrid username to use the Session as.

    Returns:
        session (shotgun_api3.Shotgun): A Shotgrid API Session.

    Raises:
        AuthenticationFault: If the authentication with Shotgrid fails.
    """

    session = shotgun_api3.Shotgun(
        base_url=shotgrid_url,
        script_name=script_name,
        api_key=api_key,
        sudo_as_login=username,
    )

    session.preferences_read()

    return session


def get_local_login():
    """Get the Shotgrid Login entry from the local registry. """
    reg = OpenPypeSettingsRegistry()
    try:
        return str(reg.get_item("shotgrid_login"))
    except Exception:
        return None


def save_local_login(login):
    """Set the Shotgrid Login entry from the local registry. """
    reg = OpenPypeSettingsRegistry()
    reg.set_item("shotgrid_login", login)
