
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

from axiom.test.historic.stubloader import saveStub

if __name__ == '__main__':
    saveStub(createDatabase)
