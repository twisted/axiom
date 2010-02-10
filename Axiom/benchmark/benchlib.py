
"""
Helper functions useful to more than one benchmark script.
"""

import time
from itertools import count

from axiom.item import Item
from axiom.attributes import integer

class StopWatch(object):
    """
    A very basic stopwatch timer.
    """
    def __init__(self):
        self.duration = 0.0

    def start(self):
        self.started = time.time()

    def stop(self):
        self.finished = time.time()
        self.duration += (self.finished - self.started)



typeNameCounter = count(0).next

def itemTypeWithSomeAttributes(attributeTypes):
    """
    Create a new L{Item} subclass with L{numAttributes} integers in its
    schema.
    """
    class SomeItem(Item):
        typeName = 'someitem_' + str(typeNameCounter())
        for i, attributeType in enumerate(attributeTypes):
            locals()['attr_' + str(i)] = attributeType()
    return SomeItem



def createSomeItems(store, itemType, values, counter):
    """
    Create some instances of a particular type in a store.
    """
    for i in counter:
        itemType(store=store, **values)
