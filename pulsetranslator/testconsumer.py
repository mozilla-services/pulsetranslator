# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

"""Test consumer for normalized Pulse messages.

Before running this module please change the exchange location in
translatorqueues.py so you do not publish entries to the official
queues. Once done run `python setup.py develop` to setup the package.
Now the publisher can be started with `./runtranslator`.
"""

import json

from translatorqueues import TranslatorConsumer


def on_pulse_message(data, message):
    key = data['_meta']['routing_key']
    if key.startswith('build'):
        print '---------- build message received', key
    else:
        print '========== test message received', key

    print json.dumps(data, indent=2)

if __name__ == "__main__":
    pulse = TranslatorConsumer(applabel='translator_test_consumer')
    pulse.configure(topic=['build.#', 'unittest.#', 'talos.#'],
                    callback=on_pulse_message,
                    durable=False)
    pulse.listen()

