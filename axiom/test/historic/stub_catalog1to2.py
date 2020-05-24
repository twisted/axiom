# -*- test-case-name: axiom.test.historic.test_catalog1to2 -*-


from axiom.item import Item
from axiom.attributes import text
from axiom.tags import Catalog
from axiom.test.historic.stubloader import saveStub

class Dummy(Item):
    attribute = text(doc="dummy attribute")



def createDatabase(s):
    """
    Populate the given Store with a Catalog and some Tags.
    """
    c = Catalog(store=s)
    c.tag(c, "internal")
    c.tag(s, "internal")
    i = Dummy(store=s)
    c.tag(i, "external")
    c.tag(i, "green")



if __name__ == '__main__':
    saveStub(createDatabase, 6917)
