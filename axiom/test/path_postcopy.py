# -*- test-case-name: axiom.test.test_upgrading.PathUpgrade.test_postCopy -*-

from axiom.attributes import path

from axiom.item import Item

from axiom.upgrade import registerAttributeCopyingUpgrader

class Path(Item):
    """
    Trivial Item class for testing upgrading.
    """
    schemaVersion = 2
    typeName = 'test_upgrade_path'
    thePath = path()

def fixPath(it):
    """
    An example postcopy function, for fixing up an item after its attributes
    have been copied.
    """
    it.thePath = it.thePath.child("foo")

registerAttributeCopyingUpgrader(Path, 1, 2, postCopy=fixPath)
