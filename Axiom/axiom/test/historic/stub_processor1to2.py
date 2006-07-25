# -*- test-case-name: axiom.test.historic.test_processor1to2 -*-

from axiom.item import Item
from axiom.attributes import text
from axiom.batch import processor

from axiom.test.historic.stubloader import saveStub


class Dummy(Item):
    __module__ = 'axiom.test.historic.stub_processor1to2'
    typeName = 'axiom_test_historic_stub_processor1to2_dummy'

    attribute = text()


DummyProcessor = processor(Dummy)


def createDatabase(s):
    """
    Put a processor of some sort into a Store.
    """
    t = DummyProcessor(store=s)
    print t.typeName


if __name__ == '__main__':
    saveStub(createDatabase, 7973)
