from axiom import item, attributes

class Bucket(item.Item):
    typeName = 'bucket'
    schemaVersion = 1

    name = attributes.text()

    def getstuff(self):
        for food in self.store.query(FoodItem,
                                     FoodItem.bucket == self,
                                     sort=FoodItem.deliciousness.descending):
            food.extra.what()


class FoodItem(item.Item):
    typeName = 'food'
    schemaVersion = 1

    bucket = attributes.reference()
    extra = attributes.reference()
    deliciousness = attributes.integer(indexed=True)

class Chicken(item.Item):
    typeName = 'chicken'
    schemaVersion = 1

    epistemologicalBasisForCrossingTheRoad = attributes.text()
    def what(self):
        print 'chicken!'

class Biscuit(item.Item):
    typeName = 'biscuit'
    schemaVersion = 1

    fluffiness = attributes.integer()
    def what(self):
        print 'biscuits!'


from axiom.store import Store

s = Store()

u = Bucket(name=u'whatever', store=s)
c = Chicken(epistemologicalBasisForCrossingTheRoad=u'extropian', store=s)
b = Biscuit(fluffiness=100, store=s)

FoodItem(store=s, deliciousness=3, extra=c, bucket=u)
FoodItem(store=s, deliciousness=4, extra=b, bucket=u)

u.getstuff()
