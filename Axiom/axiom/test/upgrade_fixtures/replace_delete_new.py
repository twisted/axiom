# -*- test-case-name: axiom.test.test_upgrading.DuringUpgradeTests.test_cascadingDeletedReferenceModifiedByForeignUpgrader -*-

from axiom.attributes import reference, integer
from axiom.item import Item, normalize
from axiom.upgrade import registerUpgrader

NEW_VALUE = 71

class Referrer(Item):
    """
    An item which just refers to another kind of item which will be upgraded.
    """
    # Don't import the old schema. -exarkun
    typeName = normalize(
        "axiom.test.upgrade_fixtures.replace_delete_old.Referrer")
    referee = reference(whenDeleted=reference.CASCADE)


class Referee(Item):
    """
    An item the upgrader of which replaces itself on L{Referrer} with a new
    instance with a different value.
    """
    # Don't import the old schema. -exarkun
    typeName = normalize(
        "axiom.test.upgrade_fixtures.replace_delete_old.Referee")
    schemaVersion = 2
    value = integer()


def referee1to2(oldReferee):
    """
    Find the L{Referrer} which refers to C{oldReferee} and replace its
    C{referee} attribute with a new, different L{Referee} item with a different
    C{value}, and which deletes the original L{Referee}.
    """
    store = oldReferee.store
    [referrer] = list(store.query(Referrer, Referrer.referee == oldReferee))
    referrer.referee = Referee(store=store, value=NEW_VALUE)
    oldReferee.deleteFromStore()

registerUpgrader(referee1to2, Referee.typeName, 1, 2)
