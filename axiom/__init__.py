# -*- test-case-name: axiom.test -*-
from axiom._version import __version__

def asTwistedVersion(packageName, versionString):
    from twisted.python import versions
    import re
    return versions.Version(
        packageName,
        *map(int, re.match(r"[0-9.]*", versionString).group().split(".")[:3]))

version = asTwistedVersion("axiom", __version__)
