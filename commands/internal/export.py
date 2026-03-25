"""
########## Export Command: Set or Display Environment Variables ##########
"""

from sshserver.sessions import get_current_session
from sshserver.environment import UserEnvironment


########## Export Command Implementation ##########
def export(username: str, *args) -> str:
    """
    ########## Set or Display Environment Variables ##########
    
    Sets environment variables based on provided arguments or displays all current variables.
    Supports both setting individual variables and displaying the full environment.
    """

    if not args:
        # ########## No Arguments: Show All Environment Variables ##########
        session = get_current_session()
        env = session.extra.get('env') if session else None
        if not env:
            return "No environment set.\n"
        # ########## Convert Dictionary to UserEnvironment Object ##########
        if isinstance(env, dict):
            env = UserEnvironment()
            for k, v in env.items():
                env.set(k, v)
            session.extra['env'] = env
        # ########## Display All Variables ##########
        lines = [f"{k}={v}" for k, v in env._vars.items()]  # access to protected attribute, but acceptable for simplicity
        return "\n".join(lines) + "\n" if lines else "No variables set.\n"

    # ########## Process Arguments: Set Environment Variables ##########
    # Combine all arguments into one line to support spaces
    line = ' '.join(args)
    session = get_current_session()
    env = session.extra.get('None') if session else None
    if not env:
        env = UserEnvironment()
        session.extra['env'] = env
    elif isinstance(env, dict):
        # ########## Convert Dictionary to UserEnvironment Object ##########
        new_env = UserEnvironment()
        for k, v in env.items():
            new_env.set(k, v)
        env = new_env
        session.extra['env'] = env

    # ########## Use UserEnvironment's export Method ##########
    result = env.export(line)
    if result:
        return result
    return "Environment variables set.\n"


########## Command Definition ##########
command = {
    "name": "export",
    "help": "Set or display environment variables",
    "func": export
}
