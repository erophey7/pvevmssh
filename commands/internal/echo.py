"""
########## Echo Command: Output Arguments with Environment Variable Support ##########
"""

import re
from sshserver.sessions import get_current_session


########## Echo Command Implementation ##########


def echo(username: str, *args) -> str:
    """
    ########## Display Arguments with Environment Variable Expansion ##########
    
    Outputs the provided arguments with support for environment variable expansion.
    Options:
      -n   Do not add a newline at the end
      -E   Disable escape sequence interpretation (enabled by default)
    """

    if not args:
        return ""

    # ########## Parse Command-Line Options ##########
    no_newline = True
    interpret = True  
    output_args = []
    for arg in args:
        if arg == "-n":
            no_newline = False
        elif arg == "-E":
            interpret = False
        else:
            output_args.append(arg)

    # ########## Retrieve Current Session and Environment Variables ##########
    session = get_current_session()
    env = session.extra.get('env') if session else None

    # ########## Function to Expand Environment Variables ##########
    def expand_vars(text: str) -> str:
        """
        ########## Substitute Environment Variables ##########
        
        Replaces occurrences of $VAR with the corresponding value from the environment.
        Supports both new (UserEnvironment class) and old (dictionary) format environments.
        """
        if not env:
            return text
        # If env is a UserEnvironment instance, use its substitute method
        if hasattr(env, 'substitute'):
            return env.substitute(text)
        # If env is a dictionary (old format), perform manual substitution
        for key, val in env.items():
            text = text.replace(f"${key}", val)
        return text

    # ########## Function to Strip Quotes from Arguments ##########
    def strip_quotes(s: str) -> str:
        """
        ########## Remove Surrounding Quotes ##########
        
        Removes leading and trailing double quotes or single quotes
        if the string is completely enclosed in them.
        """
        if (s.startswith('"') and s.endswith('"')) or \
           (s.startswith("'") and s.endswith("'")):
            return s[1:-1]
        return s

    # ########## Process Each Argument ##########
    result_parts = []
    for arg in output_args:
        # Remove surrounding quotes
        arg = strip_quotes(arg)
        # Expand environment variables
        arg = expand_vars(arg)
        # Interpret escape sequences if enabled
        if interpret:
            arg = arg.replace('\\n', '\n')
            arg = arg.replace('\\t', '\t')
            arg = arg.replace('\\r', '\r')
            arg = arg.replace('\\\\', '\\')
        result_parts.append(arg)

    output = ' '.join(result_parts)
    if not no_newline:
        output += '\n'
    return output


########## Command Definition ##########


command = {
    "name": "echo",
    "help": "Display arguments with variable expansion (default: interpret escapes)",
    "func": echo
}
