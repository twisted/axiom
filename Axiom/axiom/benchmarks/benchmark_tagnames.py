
"""
Benchmark the tagNames method of L{axiom.tags.Catalog}
"""

import time, sys

from epsilon.scripts import benchmark

from axiom import store, item, attributes, tags

N_TAGS = 20
N_COPIES = 5000
N_LOOPS = 1000

class TaggedObject(item.Item):
    name = attributes.text()



def main():
    s = store.Store("tags.axiom")
    c = tags.Catalog(store=s)
    o = TaggedObject(store=s)

    def tagObjects(tag, copies):
        for x in xrange(copies):
            c.tag(o, tag)
    for i in xrange(N_TAGS):
        s.transact(tagObjects, unicode(i), N_COPIES)

    def getTags():
        for i in xrange(N_LOOPS):
            list(c.tagNames())

    benchmark.start()
    s.transact(getTags)
    benchmark.stop()



if __name__ == '__main__':
    main()
