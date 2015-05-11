# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import ConfigParser
import optparse
import os

from mozillapulse.config import PulseConfiguration

from daemon import createDaemon
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
    parser.add_option('--durable',
                      dest='durable',
                      action='store_true',
                      default=False,
                      help='register a durable queue')
    parser.add_option('--display-only',
                      dest='display_only',
                      action='store_true',
                      default=False,
                      help='only display build properties and don\'t add '
                      'jobs to the queue')
    parser.add_option('--pulse-cfg',
                      dest='pulse_cfg',
                      default='',
                      help='optional config file containing optional sections '
                      '[consumer] and [publisher] for nondefault Pulse '
                      'configs')
    parser.add_option('--push-message',
                      dest='message',
                      help='path to file of a Pulse message to process')
    parser.add_option('--label',
                      dest='label',
                      help='label to use for pulse queue')

    options, args = parser.parse_args()

    pulse_cfgs = {'consumer': None, 'publisher': None}
    if options.pulse_cfg:
        if not os.path.exists(options.pulse_cfg):
            print 'Config file does not exist!'
            return
        pulse_cfgfile = ConfigParser.ConfigParser()
        pulse_cfgfile.read(options.pulse_cfg)
        for section in pulse_cfgs.keys():
            pulse_cfgs[section] = PulseConfiguration.read_from_config(
                pulse_cfgfile, section)
        if os.environ.get('pulseuser'):
          setattr(pulse_cfgs['consumer'], 'user', os.environ['pulseuser'])
          setattr(pulse_cfgs['publisher'], 'user', os.environ['pulseuser'])
        if os.environ.get('pulsepassword'):
          setattr(pulse_cfgs['consumer'], 'password', os.environ['pulsepassword'])
          setattr(pulse_cfgs['publisher'], 'password', os.environ['pulsepassword'])

    if options.daemon:
        if os.access(options.logfile, os.F_OK):
            os.remove(options.logfile)
        createDaemon(options.pidfile, options.logfile)

        f = open(options.pidfile, 'w')
        f.write("%d\n" % os.getpid())
        f.close()

    service = PulseBuildbotTranslator(durable=options.durable,
                                      logdir=options.logdir,
                                      message=options.message,
                                      label=options.label,
                                      display_only=options.display_only,
                                      consumer_cfg=pulse_cfgs['consumer'],
                                      publisher_cfg=pulse_cfgs['publisher'])
    service.start()

if __name__ == "__main__":
    main()
