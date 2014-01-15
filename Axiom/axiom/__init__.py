# -*- test-case-name: axiom.test -*-
from axiom._version import __version__
from twisted.python import versions

def asTwistedVersion(packageName, versionString):
    return versions.Version(packageName, *map(int, versionString.split(".")))

version = asTwistedVersion("axiom", __version__)
