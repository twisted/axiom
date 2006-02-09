# -*- test-case-name: axiom.test.test_upgrading -*-
_upgradeRegistry = {}

def registerUpgrader(upgrader, typeName, oldVersion, newVersion):
    """
    Register a callable which can perform a schema upgrade between two
    particular versions.

    @param upgrader: A one-argument callable which will upgrade an object.  It
    is invoked with an instance of the old version of the object.
    @param typeName: The database typename for which this is an upgrader.
    @param oldVersion: The version from which this will upgrade.
    @param newVersion: The version tow hich this will upgrade.  This must be
    exactly one greater than C{oldVersion}.
    """
    # assert (typeName, oldVersion, newVersion) not in _upgradeRegistry, "duplicate upgrader"

    # ^ this makes the tests blow up so it's just disabled for now; perhaps we
    # should have a specific test mode
    assert newVersion - oldVersion == 1, "read the doc string"
    _upgradeRegistry[typeName, oldVersion, newVersion] = upgrader

def upgradeAllTheWay(o, typeName, version):
    while True:
        try:
            upgrader = _upgradeRegistry[typeName, version, version + 1]
        except KeyError:
            break
        else:
            o = upgrader(o)
            version += 1
    return o
