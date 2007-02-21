
import os
import sys
import shutil
import tarfile
import inspect

from twisted.trial import unittest
from twisted.application.service import IService

from axiom.store import Store

def saveStub(funcobj, revision):
    """
    Create a stub database and populate it using the given function.

    @param funcobj: A one-argument callable which will be invoked with an Axiom
    Store instance and should add to it the old state which will be used to
    test an upgrade.

    @param revision: An SVN revision of trunk at which it was possible it is
    possible for funcobj to create the necessary state.
    """
    # You may notice certain files don't pass the second argument.  They don't
    # work any more.  Please feel free to update them with the revision number
    # they were created at.
    filename = inspect.getfile(funcobj)
    dbfn = os.path.join(
        os.path.dirname(filename),
        os.path.basename(filename).split("stub_")[1].split('.py')[0]+'.axiom')

    s = Store(dbfn)
    s.transact(funcobj, s)

    s.close()
    tarball = tarfile.open(dbfn+'.tbz2', 'w:bz2')
    tarball.add(os.path.basename(dbfn))
    tarball.close()
    shutil.rmtree(dbfn)



class StubbedTest(unittest.TestCase):

    def openLegacyStore(self):
        """
        Extract the Store tarball associated with this test, open it, and return
        it.
        """
        temp = self.mktemp()
        f = sys.modules[self.__module__].__file__
        dfn = os.path.join(
            os.path.dirname(f),
            os.path.basename(f).split("test_")[1].split('.py')[0]+'.axiom')
        arcname = dfn + '.tbz2'
        tarball = tarfile.open(arcname, 'r:bz2')
        for member in tarball.getnames():
            tarball.extract(member, temp)
        return Store(os.path.join(temp, os.path.basename(dfn)))


    def setUp(self):
        """
        Prepare to test a stub by opening and then fully upgrading the legacy
        store.
        """
        self.store = self.openLegacyStore()
        self.service = IService(self.store)
        self.service.startService()
        return self.store.whenFullyUpgraded()


    def tearDown(self):
        return self.service.stopService()
