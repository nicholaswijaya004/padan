from importlib.metadata import version

import padan


def test_package_is_installed_from_src() -> None:
    # Fails if the src layout is misconfigured and `padan` is not installed into the venv.
    assert padan.__file__ is not None
    assert "/src/padan/" in padan.__file__.replace("\\", "/")


def test_version_is_single_sourced_from_pyproject() -> None:
    assert padan.__version__ == version("padan")
