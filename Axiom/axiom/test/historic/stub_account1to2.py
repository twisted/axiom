import os
import shutil
import tarfile

from axiom.store import Store
from axiom.userbase import LoginSystem
from axiom.test.test_userbase import GarbageProtocolHandler

def createDatabase(s):
    ls = LoginSystem(store=s)
    ls.installOn(s)
    acc = ls.addAccount(u'test', u'example.com', 'asdf')
    ss = acc.avatars.open()
    gph = GarbageProtocolHandler(store=ss, garbage=7)
    gph.installOn(ss)
    # ls.addAccount(u'test2', u'example.com', 'ghjk')

# Below here should eventually be framework code.

def determineFile(f):
    return os.path.join(
        os.path.dirname(f),
        os.path.basename(f).split("stub_")[1].split('.py')[0]+'.axiom')

if __name__ == '__main__':
    dbfn = determineFile(__file__)
    s = Store(dbfn)
    s.transact(createDatabase, s)
    s.close()
    tarball = tarfile.open(dbfn+'.tbz2', 'w:bz2')
    tarball.add(os.path.basename(dbfn))
    tarball.close()
    shutil.rmtree(dbfn)
