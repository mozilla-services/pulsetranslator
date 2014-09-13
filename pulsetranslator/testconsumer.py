# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

"""Test consumer for normalized Pulse messages.

Before running this module please change the exchange location in
translatorqueues.py so you do not publish entries to the official
queues. Once done run `python setup.py develop` to setup the package.
Now the publisher can be started with `./runtranslator`.
"""

import ConfigParser
import json
import optparse
import os.path
import uuid

from mozillapulse.config import PulseConfiguration
from mozillapulse.consumers import NormalizedBuildConsumer


def on_pulse_message(data, message):
    key = data['_meta']['routing_key']
    if key.startswith('build'):
        print '---------- build message received', key
    else:
        print '========== test message received', key

    print json.dumps(data, indent=2)


def main():
    parser = optparse.OptionParser()
    parser.add_option('--pulse-cfg', dest='pulse_cfg', default='',
                      help='Pulse config')
    parser.add_option('--pulse-cfg-section', dest='pulse_cfg_section',
                      default='pulse', help='Pulse config section')
    options, args = parser.parse_args()

    pulse = NormalizedBuildConsumer(applabel='translator_test_consumer_%s'
                                    % uuid.uuid4(), connect=False)
    pulse.configure(topic=['build.#', 'unittest.#', 'talos.#'],
                    callback=on_pulse_message,
                    durable=False)
    if options.pulse_cfg:
        if not os.path.exists(options.pulse_cfg):
            print 'Config file does not exist!'
            return
        cfg = ConfigParser.ConfigParser()
        cfg.read(options.pulse_cfg)
        pulse.config = PulseConfiguration.read_from_config(
            cfg, options.pulse_cfg_section)

    pulse.listen()


if __name__ == '__main__':
    main()
