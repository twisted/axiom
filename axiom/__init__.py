# -*- test-case-name: axiom.test -*-
from twisted.python import versions
from axiom._version import __version__

def _asTwistedVersion(packageName, versionString):
    return versions.Version(packageName, *map(int, versionString.split(".")))

version = _asTwistedVersion("axiom", __version__)
