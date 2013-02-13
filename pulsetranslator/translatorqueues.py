# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
from mozillapulse.config import PulseConfiguration
from mozillapulse.consumers import GenericConsumer
from mozillapulse.messages.base import GenericMessage
from mozillapulse.publishers import GenericPublisher
import time
import traceback


def publish_message(publisherClass, logger, data, routing_key):
    publisher = publisherClass()
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
            logger.exception(routing_key)
            traceback.print_exc()
            now = datetime.datetime.now()
            failures = [x for x in failures
                        if now - x < datetime.timedelta(seconds=60)]
            failures.append(now)
            if len(failures) >= 5:
                failures = []
                time.sleep(5 * 60)
            else:
                time.sleep(5)


class TranslatorPublisher(GenericPublisher):
    def __init__(self, **kwargs):
        GenericPublisher.__init__(self,
                                  PulseConfiguration(**kwargs),
                                  'foo.org.mozilla.exchange.build.normalized')

class TranslatorConsumer(GenericConsumer):
    def __init__(self, **kwargs):
        GenericConsumer.__init__(self,
                                 PulseConfiguration(**kwargs),
                                 'foo.org.mozilla.exchange.build.normalized',
                                 **kwargs)
