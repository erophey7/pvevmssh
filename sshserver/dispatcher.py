import asyncio
import importlib
import pkgutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

############ Command Dispatcher Core Module ############
class CommandDispatcher:
    def __init__(self, username: str) -> None:
        """
        ########## Command Dispatcher Initialization ##########
        
        Initializes the command dispatcher with a username.
        Loads all available commands from the commands package.
        
        Parameters:
            username (str): Username of the connected client
        """
        self.username = username
        self.commands = {}
        self._load_commands()

    def _load_commands(self) -> None:
        """########## Command Package Loader ##########
        
        Loads all command modules from the 'commands' package.
        Iterates through subpackages and loads their commands.
        """
        commands_package = "commands"
        base_path = Path(__file__).parent.parent / commands_package

        # ########## Iterate Through Subpackages ##########
        for finder, module_name, ispkg in pkgutil.iter_modules([str(base_path)]):
            if ispkg:
                subpackage = f"{commands_package}.{module_name}"
                self._load_commands_from_package(subpackage)

        logger.debug("Loaded commands: %s", list(self.commands.keys()))

    def _load_commands_from_package(self, package_name: str) -> None:
        """########## Command Module Loader ##########
        
        Loads command modules from a specific package.
        Handles module imports and command registration.
        """
        try:
            package = importlib.import_module(package_name)
        except Exception as e:
            logger.error("Failed to import package %s: %s", package_name, e)
            return

        # ########## Iterate Through Module Files ##########
        for _, module_name, _ in pkgutil.iter_modules(package.__path__):
            full_name = f"{package_name}.{module_name}"
            try:
                module = importlib.import_module(full_name)
            except Exception as e:
                logger.error("Failed to import module %s: %s", full_name, e)
                continue

            if hasattr(module, "command"):
                cmd_name = module.command.get("name", module_name)
                self.commands[cmd_name] = module.command
                logger.debug("Loaded command: %s from %s", cmd_name, full_name)

    async def handle(self, input_line: str) -> str:
        """########## Command Line Handler ##########
        
        Processes an input line and executes the corresponding command.
        Supports help commands and handles unknown commands gracefully.
        
        Parameters:
            input_line (str): The input string from the user
            
        Returns:
            str: The result of the executed command or error message
        """
        parts = input_line.split()
        if not parts:
            return ""

        cmd_name = parts[0]
        args = parts[1:]

        if cmd_name == "help":
            return self._help()

        if cmd_name not in self.commands:
            return f"Unknown command: {cmd_name}. Type 'help' for available commands."

        cmd = self.commands[cmd_name]
        try:
            if asyncio.iscoroutinefunction(cmd["func"]):
                result = await cmd["func"](self.username, *args)
            else:
                result = cmd["func"](self.username, *args)
            return result
        except Exception as e:
            logger.exception("Error executing command %s", cmd_name)
            return f"Error executing command: {e}"

    def _help(self) -> str:
        lines = ["Available commands:"]
        for name, cmd in sorted(self.commands.items()):
            help_text = cmd.get("help", "No description")
            lines.append(f"  {name:<15} - {help_text}")
        return "\n".join(lines)