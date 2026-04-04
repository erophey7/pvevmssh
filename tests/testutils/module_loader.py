import sys
import types
import pathlib
import importlib.util


def ensure_sys_path(path: pathlib.Path) -> None:
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def ensure_pkg(name: str, path: pathlib.Path):
    if name in sys.modules:
        return sys.modules[name]

    mod = types.ModuleType(name)
    mod.__path__ = [str(path)]
    sys.modules[name] = mod
    return mod


def ensure_package_tree(root_name: str, root_path: pathlib.Path, *subpackages: str):
    ensure_pkg(root_name, root_path)

    for subpkg in subpackages:
        full_name = f"{root_name}.{subpkg}"
        full_path = root_path / subpkg.replace(".", "/")
        ensure_pkg(full_name, full_path)


def load_module(fullname: str, file_path: pathlib.Path):
    if fullname in sys.modules:
        return sys.modules[fullname]

    spec = importlib.util.spec_from_file_location(fullname, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {fullname} from {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[fullname] = module
    spec.loader.exec_module(module)
    return module


def load_package(fullname: str, package_dir: pathlib.Path):
    """
    Загружает package по __init__.py, чтобы работали относительные импорты
    внутри пакета.
    """
    if fullname in sys.modules:
        return sys.modules[fullname]

    init_file = package_dir / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        fullname,
        str(init_file),
        submodule_search_locations=[str(package_dir)],
    )

    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load package {fullname} from {package_dir}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[fullname] = module
    spec.loader.exec_module(module)
    return module


def load_modules(module_map: dict[str, pathlib.Path]):
    loaded = {}
    for fullname, file_path in module_map.items():
        loaded[fullname] = load_module(fullname, file_path)
    return loaded