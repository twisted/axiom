from axiom import attributes, item

class Measurement(item.Item):
    typeName = "measurement"

    temperature = attributes.point4decimal()
    pressure = attributes.point4decimal()
