
"""
Benchmark the tagsOf method of L{axiom.tags.Catalog}
"""

import time, sys

from epsilon.scripts import benchmark

from axiom import store, item, attributes, tags

N = 30

class TaggedObject(item.Item):
    name = attributes.text()



def main():
    s = store.Store("tags.axiom")
    c = tags.Catalog(store=s)

    objects = []
    def createObjects():
        for x in xrange(N):
            objects.append(TaggedObject(store=s))
    s.transact(createObjects)

    def tagObjects():
        for o in objects:
            for x in xrange(N):
                c.tag(o, unicode(x))
    s.transact(tagObjects)

    def getTags():
        for i in xrange(N):
            for o in objects:
                for t in c.tagsOf(o):
                    pass

    benchmark.start()
    s.transact(getTags)
    benchmark.stop()



if __name__ == '__main__':
    main()
