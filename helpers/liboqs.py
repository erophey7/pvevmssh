import os
import sys
import ctypes
import logging
from pathlib import Path

from helpers.path import Paths

logger = logging.getLogger(__name__)


def _resolve_liboqs_prefix(config=None) -> Path:
    """
    Resolve liboqs prefix from config or fallback to default path.

    Priority:
    1. config ssh.liboqs_prefix, if ssh.liboqs_custom_prefix = True
    2. Paths.LIBOQS_DEFAULT_PREFIX
    """
    default_prefix = Paths.LIBOQS_DEFAULT_PREFIX

    if config is None:
        return default_prefix.resolve()

    use_custom = config.get("ssh.liboqs_custom_prefix", False)
    custom_prefix = config.get("ssh.liboqs_prefix", str(default_prefix))

    if use_custom and custom_prefix:
        return Path(custom_prefix).expanduser().resolve()

    return default_prefix.resolve()


def _candidate_library_paths(prefix: Path) -> list[Path]:
    """
    Return possible liboqs shared library locations.
    """
    candidates = []

    for base in (prefix / "lib", prefix / "lib64"):
        candidates.extend([
            base / "liboqs.so",
            base / "liboqs.so.0",
            base / "liboqs.so.1",
        ])

        if base.exists():
            candidates.extend(sorted(base.glob("liboqs.so*")))

    seen = set()
    unique = []

    for path in candidates:
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)

    return unique


def _can_load_liboqs(name: str = "liboqs.so") -> bool:
    """
    Check whether liboqs can be loaded by the dynamic loader.
    """
    try:
        ctypes.CDLL(name)
        return True
    except OSError:
        return False


#def _prepare_liboqs_build_plan(prefix: Path) -> dict:
#    """
#    Prepare future liboqs auto-build metadata.
#
#    This function does not build anything yet.
#    It only returns a build plan for future use.
#    """
#    return {
#        "enabled": False,  # future toggle
#        "source_dir": prefix / "src" / "liboqs",
#        "build_dir": prefix / "build",
#        "install_prefix": prefix,
#        "expected_lib_dirs": [
#            prefix / "lib",
#            prefix / "lib64",
#        ],
#        "cmake_args": [
#            f"-DCMAKE_INSTALL_PREFIX={prefix}",
#            "-DBUILD_SHARED_LIBS=ON",
#            "-DOQS_BUILD_ONLY_LIB=ON",
#        ],
#    }


def ensure_liboqs(config=None) -> bool:
    """
    Ensure liboqs is available if possible.

    Behavior:
    - If system liboqs is already loadable -> return True
    - Else try configured/default prefix
    - If found there -> inject LD_LIBRARY_PATH and restart process
    - If unavailable or still unloadable -> warn and continue

    Returns:
        bool:
            True  -> liboqs is available
            False -> liboqs is not available, but execution continues
    """
    prefix = _resolve_liboqs_prefix(config)
    #build_plan = _prepare_liboqs_build_plan(prefix)

    logger.debug("Resolved liboqs prefix: %s", prefix)
    #logger.debug("Prepared liboqs build plan (inactive): %s", build_plan)

    # 1) Already available system-wide
    if _can_load_liboqs("liboqs.so"):
        logger.info("liboqs detected in system library paths")
        return True

    logger.warning("liboqs not found in system library paths, trying configured prefix")

    # 2) Search in configured prefix
    candidates = _candidate_library_paths(prefix)
    existing = next((p for p in candidates if p.is_file()), None)

    if existing is None:
        logger.warning(
            "liboqs shared library not found. "
            "Checked system paths and configured prefix: %s",
            prefix,
        )
        logger.debug("Checked candidate paths: %s", [str(p) for p in candidates])
        logger.info("liboqs support disabled, continuing without it")
        return False

    lib_dir = str(existing.parent.resolve())
    current = os.environ.get("LD_LIBRARY_PATH", "")
    paths = [p for p in current.split(":") if p]

    # 3) Add path and restart once if needed
    if lib_dir not in paths:
        logger.info("Injecting liboqs path into LD_LIBRARY_PATH: %s", lib_dir)
        os.environ["LD_LIBRARY_PATH"] = f"{lib_dir}:{current}" if current else lib_dir

        logger.debug("Restarting process to apply LD_LIBRARY_PATH")
        os.execvpe(sys.executable, [sys.executable] + sys.argv, os.environ)

    # 4) If path is already present, try load again
    if _can_load_liboqs("liboqs.so"):
        logger.info("liboqs successfully loaded after LD_LIBRARY_PATH resolution")
        return True

    logger.warning(
        "liboqs was found at '%s', but could not be loaded. "
        "Possible causes: missing dependent libraries, broken symlink, or incompatible build.",
        existing,
    )
    logger.info("liboqs support disabled, continuing without it")
    return False