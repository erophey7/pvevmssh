"""
########## Mouse Reporting Command ##########
"""

from sshserver.sessions import get_current_session


########## Mouse Reporting Function ##########
def mouse(username: str, *args) -> str:
    """
    ########## Enable/Disable Mouse Reporting ##########
    
    Toggles mouse reporting in the terminal. Sends escape sequences to
    enable or disable mouse tracking for SSH sessions.
    
    Usage: mouse [on|off]
    """

    session = get_current_session()
    if not session:
        return "No session found.\n"
    process = session.extra.get('process')
    if not process:
        return "No process found in session.\n"

    # ########## Determine Enable/Disable State ##########
    enable = False
    if args and args[0].lower() == 'on':
        enable = True
    elif args and args[0].lower() == 'off':
        enable = False
    else:
        # ########## Default Behavior: Show Help ##########
        return "Usage: mouse on|off\n"

    # ########## Send Escape Sequences for Mouse Reporting ##########
    if enable:
        process.stdout.write("\033[?1000h")   # Enable mouse reporting
        return "Mouse reporting enabled.\n"
    else:
        process.stdout.write("\033[?1000l")   # Disable mouse reporting
        return "Mouse reporting disabled.\n"


########## Command Definition ##########
command = {
    "name": "mouse",
    "help": "Enable or disable mouse reporting",
    "func": mouse
}
