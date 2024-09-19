import shotgun_api3
from shotgun_api3.shotgun import AuthenticationFault

from ayon_core.lib import AYONSecureRegistry


def check_user_permissions(
    shotgrid_url,
    username,
    password: str = None,
    api_key: str = None,
    script_name: str = None,
    proxy: str = None,
):
    """Check if the provided user can access the Shotgrid API.

    Args:
        shotgrid_url (str): The Shotgun server URL.
        username (str): The Shotgrid username to use the Session as.
        password (Optional[str]): The Shotgrid password to use the Session as.
        api_key (Optional[str]): The Shotgrid API key to use the Session as.
        script_name (Optional[str]): The Shotgrid API script name to use the
            Session as.
        proxy (Optional[str]): The proxy to use for the connection.

    Returns:
        tuple(bool, str): Whether the connection was successful or not, and a
            string message with the result.
     """

    if not any([shotgrid_url, username]):
        return (False, "Missing a field.")

    kwargs = {}

    if api_key:
        if not script_name:
            return (
                False,
                (
                    "'script_name' input arg should be used in "
                    "combination with 'api_key'."
                )
            )
        kwargs.update({
            "api_key": api_key,
            "script_name": script_name,
        })
    if password:
        kwargs["password"] = password
    if proxy:
        kwargs["proxy"] = proxy

    try:
        session = create_sg_session(shotgrid_url, username, **kwargs)
        session.close()
    except AuthenticationFault as e:
        return (False, str(e))

    return (True, "Successfully logged in.")


def create_sg_session(
    shotgrid_url,
    username,
    password: str = None,
    api_key: str = None,
    script_name: str = None,
    proxy: str = None,
):
    """Attempt to create a Shotgun Session

    Args:
        shotgrid_url (str): The Shotgun server URL.
        username (str): The Shotgrid username to use the Session as.
        password (Optional[str]): The Shotgrid password to use the Session as.
        api_key (Optional[str]): The Shotgrid API key to use the Session as.
        script_name (Optional[str]): The Shotgrid API script name to use the
            Session as.
        proxy (Optional[str]): The proxy to use for the connection.

    Returns:
        session (shotgun_api3.Shotgun): A Shotgrid API Session.

    Raises:
        AuthenticationFault: If the authentication with Shotgrid fails.
    """
    if not any([shotgrid_url, username]):
        return (False, "Missing a field.")

    kwargs = {
        "base_url": shotgrid_url
    }

    if api_key:
        if not script_name:
            return (
                False,
                (
                    "'script_name' input arg should be used in "
                    "combination with 'api_key'."
                )
            )
        kwargs.update({
            "api_key": api_key,
            "script_name": script_name,
            "sudo_as_login": username,
        })
    if password:
        kwargs.update({
            "password": password,
            "login": username,
        })
    if proxy:
        kwargs["http_proxy"] = proxy

    session = shotgun_api3.Shotgun(**kwargs)

    session.preferences_read()

    return session


def get_local_login():
    """Get the Shotgrid Login entry from the local registry. """
    try:
        reg = AYONSecureRegistry("shotgrid/user")
        username = reg.get_item("value")
        reg = AYONSecureRegistry("shotgrid/pass")
        password = reg.get_item("value")
        return username, password
    except Exception:
        return (None, None)


def save_local_login(username, password):
    """Save the Shotgrid Login entry from the local registry. """
    reg = AYONSecureRegistry("shotgrid/user")
    reg.set_item("value", username)
    if password:
        reg = AYONSecureRegistry("shotgrid/pass")
        reg.set_item("value", password)


def clear_local_login():
    """Clear the Shotgrid Login entry from the local registry. """
    reg = AYONSecureRegistry("shotgrid/user")
    if reg.get_item("value", None) is not None:
        reg.delete_item("value")
    reg = AYONSecureRegistry("shotgrid/pass")
    if reg.get_item("value", None) is not None:
        reg.delete_item("value")
