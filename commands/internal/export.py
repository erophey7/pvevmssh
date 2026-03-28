"""
Set or display environment variables.
"""

from sshserver.session.manager import get_current_session
from sshserver.session.environment import UserEnvironment


def export(username: str, *args) -> str:
    session = get_current_session()
    if not session:
        return "No session.\n"

    env = session.extra.get('env')
    if not env or not isinstance(env, UserEnvironment):
        env = UserEnvironment()
        session.extra['env'] = env

    if not args:
        if hasattr(env, 'as_dict'):
            items = env.as_dict().items()
        elif hasattr(env, '_vars'):
            items = env._vars.items()
        else:
            return "Cannot retrieve environment variables.\n"
        lines = [f"{k}={v}" for k, v in items]
        return "\n".join(lines) + "\n" if lines else "No variables set.\n"

    results = []
    for arg in args:
        if "=" not in arg:
            continue
        key, value = arg.split("=", 1)
        env.set(key, value)
        results.append(f"{key}={value}")

    return "Environment variables set: " + ", ".join(results) + "\n"


command = {
    "name": "export",
    "help": "Set or display environment variables",
    "func": export
}