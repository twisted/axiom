
"""
Benchmark creation of a large number of simple Items in a transaction.
"""

from epsilon.scripts import benchmark

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

    benchmark.start()
    s.transact(txn)
    benchmark.stop()


if __name__ == '__main__':
    main()
