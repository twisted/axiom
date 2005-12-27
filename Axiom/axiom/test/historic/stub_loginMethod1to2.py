import os
import shutil
import tarfile

from axiom.store import Store
from axiom.userbase import LoginSystem
from axiom.test.test_userbase import GarbageProtocolHandler
from axiom.test.historic.test_loginMethod1to2 import CREDENTIALS, GARBAGE_LEVEL

def createDatabase(s):
    ls = LoginSystem(store=s)
    ls.installOn(s)
    acc = ls.addAccount(*CREDENTIALS)
    ss = acc.avatars.open()
    gph = GarbageProtocolHandler(store=ss, garbage=GARBAGE_LEVEL)
    gph.installOn(ss)

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
