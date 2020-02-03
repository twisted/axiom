# -*- test-case-name: axiom.test.historic.test_textlist -*-


from axiom.item import Item
from axiom.attributes import textlist
from axiom.test.historic.stubloader import saveStub

class Dummy(Item):
    typeName = 'axiom_textlist_dummy'
    schemaVersion = 1

    attribute = textlist(doc="a textlist")



def createDatabase(s):
    """
    Populate the given Store with some Dummy items.
    """
    Dummy(store=s, attribute=[u'foo', u'bar'])



if __name__ == '__main__':
    saveStub(createDatabase, 11858)
