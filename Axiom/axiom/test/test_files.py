
import os

from twisted.trial import unittest

from twisted.python.filepath import FilePath

from axiom.store import Store

from axiom.item import Item
from axiom.attributes import path

class PathTesterItem(Item):
    schemaVersion = 1
    typeName = 'test_path_thing'

    relpath = path()
    abspath = path(relative=False)



class InStoreFilesTest(unittest.TestCase):

    def testCreateFile(self):
        s = Store(self.mktemp())
        f = s.newFile('test', 'whatever.txt')
        f.write('crap')
        def cb(fpath):
            self.assertEquals(fpath.open().read(), 'crap')

        return f.close().addCallback(cb)


class PathAttributesTest(unittest.TestCase):
    def testRelocatingPaths(self):
        spath = self.mktemp()
        npath = self.mktemp()
        s = Store(spath)
        rel = s.newFile("test", "123")
        TEST_STR = "test 123"

        def cb(fpath):
            fpath.open("w").write(TEST_STR)

            PathTesterItem(store=s,
                           relpath=fpath)

            s.close()
            os.rename(spath, npath)
            s2 = Store(npath)
            pti = list(s2.query(PathTesterItem))[0]

            self.assertEquals(pti.relpath.open().read(),
                              TEST_STR)

        return rel.close().addCallback(cb)
