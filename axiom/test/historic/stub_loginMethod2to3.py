from axiom.test.historic.stub_loginMethod1to2 import createDatabase as cD

def createDatabase(store):
    #mumble, frotz, gotta pass a different funcobj than the imported
    #one to saveStub
    cD(store)
    
from axiom.test.historic.stubloader import saveStub

if __name__ == '__main__':
    saveStub(createDatabase, 7740)
