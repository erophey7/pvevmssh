# sshserver/session/shell_lsp.py

class ShellLSP:
    def register(self, engine):
        engine.register_command("help")
        engine.register_command("exit")
        engine.register_command("clear")
        engine.register_command("history")

        engine.register_command(
            "ls",
            ["-l", "-a", "--color", "-h", "--human-readable"]
        )

        engine.register_command("cd")
        engine.register_command("pwd")

        engine.register_command(
            "vm",
            ["list", "start", "stop", "status", "console", "info", "migrate"]
        )

        engine.register_command(
            "pve",
            ["vm", "node", "storage", "cluster", "task", "user"]
        )

        engine.register_global_words([
            "status", "whoami", "date", "uptime", "free", "df", "top",
            "reboot", "shutdown", "poweroff",
            "help", "clear", "history"
        ])