
from twisted.trial import unittest

from axiom.store import Store
from axiom.tags import Catalog

from axiom.item import Item
from axiom.attributes import text

class Gizmo(Item):
    typeName = 'test_gizmo'
    schemaVersion = 1
    name = text()



class TagTestCase(unittest.TestCase):

    def testTagging(self):
        s = Store()
        c = Catalog(store=s)
        g1 = Gizmo(store=s, name=u'one')
        g2 = Gizmo(store=s, name=u'two')

        c.tag(g1, u'single')
        c.tag(g1, u'multi')
        c.tag(g2, u'multi')
        c.tag(g1, u'multi')

        self.assertEquals(list(c.tagsOf(g1)),
                          [u'single', u'multi'])
        self.assertEquals(list(c.tagsOf(g2)),
                          [u'multi'])

        self.assertEquals(list(c.objectsIn(u'single')), [g1])
        self.assertEquals(list(c.objectsIn(u'multi')), [g1, g2])
