# -*- test-case-name: axiom.test.test_upgrading.DuringUpgradeTests.test_referenceModifiedByForeignUpgrader -*-

from axiom.attributes import reference, integer
from axiom.item import Item

OLD_VALUE = 69

class Referrer(Item):
    """
    An item which just refers to another kind of item which will be upgraded.
    """
    referee = reference()


class Referee(Item):
    """
    An item the upgrader of which replaces itself on L{Referrer} with a new
    instance with a different value.
    """
    value = integer()
