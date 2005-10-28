
from axiom import item, attributes

class PlainItem(item.Item):
    typeName = 'axiom_test_plain_item'
    schemaVersion = 1

    plain = attributes.text()
