# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import calendar
import json
import time

import requests

from mozillapulse.publishers import NormalizedBuildPublisher

from .translatorexceptions import LogTimeoutError
from .translatorqueues import publish_message

DEBUG = False


class LogHandler(object):

    def __init__(self, error_logger, publisher_cfg):
        self.error_logger = error_logger
        self.publisher_cfg = publisher_cfg

    def get_url_info(self, url):
        """Return a (code, content_length) tuple from making an
           HTTP HEAD request for the given url.

        """
        try:
            resp = requests.get(url)
            resp.raise_for_status()

            # In case of a redirect make another head request for the new location.
            if resp.status_code == 301:
                resp = requests.head(resp.headers['location'])
                resp.raise_for_status()

            return (resp.status_code, resp.headers.get('Content-length'))

        except (requests.exceptions.RequestException, IOError) as e:
            self.error_logger.error('HEAD request for {} failed with "{}".'.format(url, e))
            return (-1, -1)

        except Exception:
            self.error_logger.exception('Unknown failure.')
            return (-1, -1)

    def process_data(self, data, publish_method):
        """
        Publish the message when the data is ready.

        ``publish_method`` The method to publish the type of message that
            this data is for.  Usually ``publish_unittest_message`` or
            ``publish_build_message``.
        """

        if not data.get('logurl'):
            # should log this
            return

        retrying = False

        while True:
            now = calendar.timegm(time.gmtime())

            (code, content_length) = self.get_url_info(str(data['logurl']))

            if DEBUG:
                if retrying:
                    print '...reprocessing logfile', code, data.get('logurl')
                    print '...', data.get('key')
                    print '...', now - data.get('insertion_time', 0), 'seconds since insertion_time'
                else:
                    print 'processing logfile', code, data.get('logurl')
            if code == 200:
                publish_method(data)
                break
            else:
                if now - data.get('insertion_time', 0) > 600:
                    raise LogTimeoutError(data.get('key', 'unknown'),
                                          data.get('logurl'))
                else:
                    retrying = True
                    if DEBUG:
                        print 'sleeping 15 seconds before retrying'
                    time.sleep(15)

    def publish_unittest_message(self, data):
        # The original routing key has the format build.foo.bar.finished;
        # we only use 'foo' in the new routing key.
        original_key = data['key'].split('.')[1]
        tree = data['tree']
        pltfrm = data['platform']
        buildtype = data['buildtype']
        os = data['os']
        test = data['test']
        product = data['product'] if data['product'] else 'unknown'
        key_parts = ['talos' if data['talos'] else 'unittest',
                     tree,
                     pltfrm,
                     os,
                     buildtype,
                     test,
                     product,
                     original_key]

        publish_message(NormalizedBuildPublisher, self.error_logger, data,
                        '.'.join(key_parts), self.publisher_cfg)

    def publish_build_message(self, data):
        # The original routing key has the format build.foo.bar.finished;
        # we only use 'foo' in the new routing key.
        original_key = data['key'].split('.')[1]
        tree = data['tree']
        pltfrm = data['platform']
        buildtype = data['buildtype']
        key_parts = ['build', tree, pltfrm, buildtype]
        for tag in data['tags']:
            if tag:
                key_parts.append(tag)
            if tag == 'l10n':
                key_parts.append(data['locale'])
        key_parts.append(original_key)

        publish_message(NormalizedBuildPublisher, self.error_logger, data,
                        '.'.join(key_parts), self.publisher_cfg)

    def handle_message(self, data):
        try:
            # publish the right kind of message based on the data.
            # if it's not a unittest, presume it's a build.
            if data.get("test"):
                publish_method = self.publish_unittest_message
            else:
                publish_method = self.publish_build_message
            self.process_data(data, publish_method=publish_method)
        except Exception:
            obj_to_log = data
            if (data.get('payload') and data['payload'].get('build') and
                data['payload']['build'].get('properties')):
                obj_to_log = data['payload']['build']['properties']
            self.error_logger.exception(json.dumps(obj_to_log, indent=2))
