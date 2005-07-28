
from twisted.trial import unittest

from axiom.store import Store

class InStoreFilesTest(unittest.TestCase):

    def testCreateFile(self):
        s = Store(self.mktemp())
        f = s.newFile('test', 'whatever.txt')
        f.write('crap')
        def cb(fpath):
            self.assertEquals(fpath.open().read(), 'crap')

        return f.close().addCallback(cb)
