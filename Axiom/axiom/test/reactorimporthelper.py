# Copyright 2009 Divmod, Inc.  See LICENSE file for details

"""
Helper for axiomatic reactor-selection unit tests.
"""

# The main point of this file: import the default reactor.
from twisted.internet import reactor

# Define an Item, too, so that it can go into a Store and trigger an import of
# this module at schema-check (ie, store opening) time.
from axiom.item import Item
from axiom.attributes import integer

class SomeItem(Item):
    attribute = integer()

