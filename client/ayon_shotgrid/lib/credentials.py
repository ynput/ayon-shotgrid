import shotgun_api3


def create_sg_session(shotgrid_url, username, script_name, api_key, proxy):
    """Attempt to create a Shotgun Session

    Args:
        shotgrid_url (str): The Shotgun server URL.
        username (str): The Shotgrid username to use the Session as.
        script_name (str): The Shotgrid API script name.
        api_key (str): The Shotgrid API key.
        proxy (str): The proxy address to use to connect to SG server.

    Returns:
        session (shotgun_api3.Shotgun): A Shotgrid API Session.

    Raises:
        AuthenticationFault: If the authentication with Shotgrid fails.
    """

    session = shotgun_api3.Shotgun(
        base_url=shotgrid_url,
        script_name=script_name,
        http_proxy=proxy,
        api_key=api_key,
        sudo_as_login=username,
    )

    session.preferences_read()

    return session


