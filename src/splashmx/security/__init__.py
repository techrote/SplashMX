"""SplashMX deny-by-default security boundaries.

The capability layer remains the package-level public surface. Physical security is
imported explicitly from ``splashmx.security.physical`` to avoid a package↔security
initialization cycle through the production package model.
"""

from .capabilities import *  # noqa: F401,F403
