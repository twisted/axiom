
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

from axiom.test.historic.stubloader import saveStub

if __name__ == '__main__':
    saveStub(createDatabase)
