from twisted.application import service
from axiom import store

application = service.Application('AXIOM')
store.StorageService(__file__.replace('.tac', '.axiom')).setServiceParent(application)
