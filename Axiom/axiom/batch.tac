# -*- test-case-name: axiom.test.test_batch -*-

"""
Application configuration for the batch sub-process.

This process reads commands and sends responses via stdio using the JUICE
protocol.  When it's not doing that, it queries various databases for work to
do, and then does it.  The databases which it queries can be controlled by
sending it messages.
"""

from twisted.application import service
from twisted.internet import stdio

from axiom import batch

application = service.Application("Batch Processing App")
svc = service.MultiService()
svc.setServiceParent(application)
stdio.StandardIO(batch.BatchProcessingProtocol(svc, True))
