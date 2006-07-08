# -*- test-case-name: axiom.test.test_upgrading.DeletionTest.testPowerups -*-

from axiom.item import Item
from axiom.attributes import integer

class Obsolete(Item):
    """
    This is a stub placeholder so that axiomInvalidateModule will invalidate
    the appropriate typeName; it's probably bad practice to declare recent
    versions of deleted portions of the schema, but that's not what this is
    testing.
    """
    typeName = 'test_upgrading_obsolete'
    nothing = integer()
    schemaVersion = 2

from axiom.upgrade import registerUpgrader

def obsolete1toNone(oldObsolete):
    oldObsolete.deleteFromStore()
    return None

registerUpgrader(obsolete1toNone, 'test_upgrading_obsolete', 1, 2)
