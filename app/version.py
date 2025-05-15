"""Version information."""

__version__ = "1.7.1"
VERSION = tuple(map(int, __version__.split('.')))

def get_version():
    """Return the current version string."""
    return __version__ 