# -*- test-case-name: axiom.test.historic.test_storeID -*-

from axiom.item import Item
from axiom.attributes import text
from axiom.test.historic.stubloader import saveStub


class Dummy(Item):
    typeName = 'axiom_storeid_dummy'
    schemaVersion = 1

    attribute = text(doc='text', allowNone=True)



def createDatabase(s):
    """
    Populate the given Store with some Dummy items.
    """
    Dummy(store=s, attribute=u'one')
    Dummy(store=s, attribute=u'two')
    i = Dummy(store=s, attribute=u'three')
    Dummy(store=s, attribute=u'four')
    i.deleteFromStore()



if __name__ == '__main__':
    saveStub(createDatabase, 0x1240846306fcda3289550cdf9515b2c7111d2bac)
