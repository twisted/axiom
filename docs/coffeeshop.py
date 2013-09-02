from axiom import attributes, item


class ShopItem(item.Item):
    typeName = "shop_item"

    description = attributes.text(allowNone=False)
    price = attributes.money(allowNone=False)
