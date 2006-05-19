
"""
Benchmark creation of a large number of simple Items in a transaction.
"""

from axiom.store import Store
from axiom.item import Item
from axiom.attributes import integer, text

class AB(Item):
    a = integer()
    b = text()

def main():
    s = Store("TEMPORARY.axiom")
    def txn():
        for x in range(10000):
            AB(a=x, b=unicode(x), store=s)
    s.transact(txn)
    s.close()

if __name__ == '__main__':
    main()
