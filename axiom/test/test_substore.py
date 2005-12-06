
from twisted.trial import unittest

from axiom.store import Store
from axiom.item import Item
from axiom.substore import SubStore

from axiom.attributes import text, bytes


class SubStored(Item):

    schemaVersion = 1
    typeName = 'substoredthing'
    a = text()
    b = bytes()


class SubStoreTest(unittest.TestCase):

    def testOneThing(self):
        topdb = self.mktemp()
        s = Store(topdb)
        ss = SubStore.createNew(s, ['account', 'bob@divmod.com'])
        s2 = ss.open()

        ssd = SubStored(store=s2, a=u'hello world', b='what, its text')
        oid = ss.storeID
        oid2 = ssd.storeID

        s2.close()
        s.close()

        reopens = Store(topdb)
        reopenss = reopens.getItemByID(oid)
        reopens2 = reopenss.open()
        reopenssd = reopens2.getItemByID(oid2)

        self.assertEquals(reopenssd.a, u'hello world')
        self.assertEquals(reopenssd.b, 'what, its text')


