from axiom.userbase import LoginSystem
from axiom.dependency import installOn
from axiom.test.historic.stubloader import saveStub
from axiom.test.test_userbase import GarbageProtocolHandler


def createDatabase(s):
    ls = LoginSystem(store=s)
    installOn(ls, s)
    acc = ls.addAccount(u'test', u'example.com', u'asdf')
    ss = acc.avatars.open()
    gph = GarbageProtocolHandler(store=ss, garbage=7)
    installOn(gph, ss)


if __name__ == '__main__':
    saveStub(createDatabase, 0x1240846306fcda3289550cdf9515b2c7111d2bac)
