# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import time
import traceback

from mozillapulse.messages.base import GenericMessage


def publish_message(publisherClass, logger, data, routing_key, pulse_cfg):
    publisher = publisherClass(connect=False)
    if pulse_cfg:
        publisher.config = pulse_cfg
    msg = GenericMessage()
    msg.routing_parts = routing_key.split('.')
    assert(isinstance(data, dict))
    for key, value in data.iteritems():
        msg.set_data(key, value)

    failures = []
    while True:
        # keep re-trying in case of failure
        try:
            publisher.publish(msg)
            break
        except Exception:
            now = datetime.datetime.now()
            logger.exception('[%s] %s' % (now, routing_key))
            traceback.print_exc()
            failures = [x for x in failures
                        if now - x < datetime.timedelta(seconds=60)]
            failures.append(now)
            if len(failures) >= 5:
                failures = []
                time.sleep(5 * 60)
            else:
                time.sleep(5)
