# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import time
import traceback

from mozillapulse.messages.base import GenericMessage


def publish_message(publisherClass, logger, data, routing_key, pulse_cfg):
    assert(isinstance(data, dict))

    msg = GenericMessage()
    msg.routing_parts = routing_key.split('.')
    for key, value in data.iteritems():
        msg.set_data(key, value)

    failures = []
    while True:
        try:
            publisher = publisherClass(connect=False)
            if pulse_cfg:
                publisher.config = pulse_cfg
            publisher.publish(msg)
            break
        except Exception:
            now = datetime.datetime.now()
            logger.exception('Failure when publishing %s' % routing_key)
            traceback.print_exc()

            failures = [x for x in failures
                        if now - x < datetime.timedelta(seconds=60)]
            failures.append(now)

            if len(failures) >= 5:
                failures = []
                sleep_time = 5 * 60
            else:
                sleep_time = 5

            logger.warning('Sleeping for %d seconds.' % sleep_time)
            time.sleep(sleep_time)
            logger.warning('Retrying...')
