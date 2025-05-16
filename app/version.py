"""Version information."""

__version__ = "1.0.0"
VERSION = tuple(map(int, __version__.split('.')))

def get_version():
    """Return the current version string."""
    return __version__ 