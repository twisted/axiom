
import os
import sys

from twisted.python.util import sibpath

from axiom.scripts import axiomatic

class InstallUbuntuService(axiomatic.AxiomaticCommand):
    name = 'service'

    description = 'Install a service to be run at operating-system startup'


    def postOptions(self):
        # all this junk really wants to run as a user...
        subenv = {}
        dp = self.parent.getStore().dbdir

        subenv['PYTHONPATH'] = os.environ['PYTHONPATH']
        subenv['AXIOMATIC_SCRIPT'] = os.path.abspath(sys.argv[0])
        subenv['AXIOMATIC_UID'] = os.environ.get("SUDO_UID", os.getuid())
        subenv['AXIOMATIC_GID'] = os.environ.get("SUDO_GID", os.getgid())
        subenv['AXIOMATIC_DATABASE'] = dp.path

        p = dp.child("init-script-config.sh")
        f = p.open('w')

        f.write('#!/bin/sh\n\n')

        for varname, varvalue in sorted(subenv.iteritems()):
            f.write("export %s=%r\n" % (varname, varvalue))

        f.write(". %r\n" % (sibpath(__file__, "axiom-lsb-init.sh"),))
        f.write("main $*\n")
        f.close()

        os.chmod(p.path, 0755)

        # but this can't run as anyone but root.
        os.symlink(p.path, '/etc/init.d/axiom-service')
        os.symlink('/etc/init.d/axiom-service', '/etc/rc0.d/K25axiom-service')
        os.symlink('/etc/init.d/axiom-service', '/etc/rc1.d/K25axiom-service')
        os.symlink('/etc/init.d/axiom-service', '/etc/rc6.d/K25axiom-service')
        os.symlink('/etc/init.d/axiom-service', '/etc/rc2.d/S25axiom-service')




