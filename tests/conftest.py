import pathlib

from tests.testutils.module_loader import ensure_sys_path, ensure_package_tree

ROOT = pathlib.Path(__file__).resolve().parent.parent
SSH_ROOT = ROOT / "sshserver"

ensure_sys_path(ROOT)

# Базовое дерево пакетов для тестов
ensure_package_tree(
    "sshserver",
    SSH_ROOT,
    "terminal",
    "session",
)