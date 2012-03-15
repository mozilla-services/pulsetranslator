# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.


from translatorqueues import TranslatorConsumer

def on_pulse_message(data, message):
    key = data['_meta']['routing_key']
    if key.startswith('build'):
        print '---------- build message received', key
        import json
        print json.dumps(data, indent=2)
    else:
        print '========== test message received', key

if __name__ == "__main__":
    pulse = TranslatorConsumer(applabel='translator_test_consumer')
    pulse.configure(topic=['build.#', 'unittest.#', 'talos.#'],
                    callback=on_pulse_message,
                    durable=False)
    pulse.listen()

