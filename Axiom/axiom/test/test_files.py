
import os

from twisted.trial import unittest
from twisted.python import filepath

from axiom.store import Store

from axiom.item import Item
from axiom.attributes import path

class PathTesterItem(Item):
    schemaVersion = 1
    typeName = 'test_path_thing'

    relpath = path()
    abspath = path(relative=False)



class InStoreFilesTest(unittest.TestCase):
    """
    Tests for files managed by the store.
    """
    def _testFile(self, s):
        """
        Shared part of file creation tests.
        """
        f = s.newFile('test', 'whatever.txt')
        f.write('crap')
        def cb(fpath):
            self.assertEquals(fpath.open().read(), 'crap')

        return f.close().addCallback(cb)


    def test_createFile(self):
        """
        Ensure that file creation works for on-disk stores.
        """
        s = Store(filepath.FilePath(self.mktemp()))
        return self._testFile(s)


    def test_createFileInMemory(self):
        """
        Ensure that file creation works for in-memory stores as well.
        """
        s = Store(filesdir=filepath.FilePath(self.mktemp()))
        return self._testFile(s)

    def test_createFileInMemoryAtString(self):
        """
        The 'filesdir' parameter should accept a string as well, for now.
        """
        s = Store(filesdir=self.mktemp())
        return self._testFile(s)


    def test_noFiledir(self):
        """
        File creation should raise an error if the store has no file directory.
        """
        s = Store()
        self.assertRaises(RuntimeError, s.newFile, "test", "whatever.txt")

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
