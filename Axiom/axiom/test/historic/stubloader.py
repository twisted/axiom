
from twisted.trial import unittest
from axiom.store import Store

import os
import sys
import tarfile

def determineFile(f):
    return os.path.join(
        os.path.dirname(f),
        os.path.basename(f).split("test_")[1].split('.py')[0]+'.axiom')

class StubbedTest(unittest.TestCase):
    def setUp(self):
        temp = self.mktemp()
        dfn = determineFile(sys.modules[self.__module__].__file__)
        arcname = dfn + '.tbz2'
        tarball = tarfile.open(arcname, 'r:bz2')
        for member in tarball.getnames():
            tarball.extract(member, temp)
        self.store = Store(os.path.join(temp, os.path.basename(dfn)))


