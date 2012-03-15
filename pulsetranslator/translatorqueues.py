# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from mozillapulse.config import PulseConfiguration
from mozillapulse.consumers import GenericConsumer
from mozillapulse.messages.base import GenericMessage
from mozillapulse.publishers import GenericPublisher


def publish_message(publisherClass, data, routing_key):
    publisher = publisherClass()
    msg = GenericMessage()
    msg.routing_parts = routing_key.split('.')
    assert(isinstance(data, dict))
    for key, value in data.iteritems():
        msg.set_data(key, value)
    publisher.publish(msg)

class TranlsatorPublisher(GenericPublisher):
    def __init__(self, **kwargs):
        GenericPublisher.__init__(self,
                                  PulseConfiguration(**kwargs),
                                  'org.mozilla.exchange.build.normalized')

class TranslatorConsumer(GenericConsumer):
    def __init__(self, **kwargs):
        GenericConsumer.__init__(self,
                                 PulseConfiguration(**kwargs),
                                 'org.mozilla.exchange.build.normalized',
                                 **kwargs)
