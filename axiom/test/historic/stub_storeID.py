# -*- test-case-name: axiom.test.historic.test_storeID -*-

from axiom.item import Item
from axiom.attributes import text
from axiom.test.historic.stubloader import saveStub


class Dummy(Item):
    typeName = 'axiom_storeid_dummy'
    schemaVersion = 1

    attribute = text(doc='text', allowNone=False)



class Dummy2(Item):
    typeName = 'axiom_storeid_dummy2'
    schemaVersion = 1

    attribute = text(doc='text', allowNone=False)



def createDatabase(s):
    """
    Populate the given Store with some Dummy items.
    """
    Dummy(store=s, attribute=u'one')
    Dummy(store=s, attribute=u'two')
    i = Dummy(store=s, attribute=u'three')
    Dummy2(store=s, attribute=u'four')
    # Work around https://github.com/twisted/axiom/issues/86
    i.checkpoint()
    i.deleteFromStore()



if __name__ == '__main__':
    saveStub(createDatabase, 0x1240846306fcda3289550cdf9515b2c7111d2bac)
