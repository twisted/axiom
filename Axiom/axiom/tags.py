
import itertools, operator

from epsilon.extime import Time

from axiom.item import Item
from axiom.attributes import text, reference, integer, AND, timestamp

class Tag(Item):
    typeName = 'tag'
    schemaVersion = 1
    name = text()

    created = timestamp()

    object = reference()
    catalog = reference()
    tagger = reference()

class Catalog(Item):

    typeName = 'tag_catalog'
    schemaVersion = 1

    tagCount = integer(default=0)

    def tag(self, obj, tagName, tagger=None):
        """
        """
        self.tagCount += 1
        # check to see if that tag exists:
        for t in self.store.query(Tag,
                                  AND(Tag.object == obj,
                                      Tag.name == tagName,
                                      Tag.tagger == tagger)):
            return
        Tag(store=self.store, object=obj,
            name=tagName, catalog=self,
            created=Time(), tagger=tagger)

    def tagsOf(self, obj):
        """
        Return an iterator of unicode strings (tag names).
        """
        return itertools.imap(operator.attrgetter('name'),
                              self.store.query(Tag,
                                               AND(Tag.object == obj,
                                                   Tag.catalog == self)))

    def objectsIn(self, tagName):
        return itertools.imap(operator.attrgetter('object'),
                              self.store.query(Tag,
                                               AND(Tag.name == tagName,
                                                   Tag.catalog == self)))

