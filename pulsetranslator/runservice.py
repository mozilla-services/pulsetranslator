# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from daemon import createDaemon
import optparse
import os
from pulsetranslator import PulseBuildbotTranslator

def main():
    parser = optparse.OptionParser()
    parser.add_option('--pidfile', dest='pidfile',
                      default='translator.pid',
                      help='path to file for logging pid')
    parser.add_option('--logfile', dest='logfile',
                      default='stdout.log',
                      help='path to file for stdout logging')
    parser.add_option('--logdir', dest='logdir',
                      default='logs',
                      help='directory to store other log files')
    parser.add_option('--daemon', dest='daemon', action='store_true',
                      help='run as daemon (posix only)')
    options, args = parser.parse_args()

    if options.daemon:
        if os.access(options.logfile, os.F_OK):
            os.remove(options.logfile)
        createDaemon(options.pidfile, options.logfile)

        f = open(options.pidfile, 'w')
        f.write("%d\n" % os.getpid())
        f.close()

    service = PulseBuildbotTranslator(logdir=options.logdir)
    service.start()

if __name__ == "__main__":
    main()
