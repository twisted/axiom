import sys

from axiom import store
from twisted.python import filepath

def main(storePath, itemID):

    assert 'axiom.test.itemtest' not in sys.modules, "Test is invalid."

    st = store.Store(filepath.FilePath(storePath))
    item = st.getItemByID(itemID)
    print item.plain

if __name__ == '__main__':
    main(storePath=sys.argv[1], itemID=int(sys.argv[2]))
