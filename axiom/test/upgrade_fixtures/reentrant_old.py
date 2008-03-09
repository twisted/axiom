# -*- test-case-name: axiom.test.test_upgrading.DuringUpgradeTests.test_reentrantUpgraderFailure -*-

from axiom.attributes import integer
from axiom.item import Item

class Simple(Item):
    """
    A simple item that doesn't do much.
    """
    dummy = integer()
