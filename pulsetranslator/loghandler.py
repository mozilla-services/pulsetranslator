# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import calendar
import httplib
import json
import logging
import logging.handlers
import os
import platform
from Queue import Empty
import subprocess
import sys
import time
from urlparse import urlparse

from translatorexceptions import *
from translatorqueues import *

DEBUG = False


class LogHandler(object):

    def __init__(self, queue, parent_pid, logdir):
        self.queue = queue
        self.parent_pid = parent_pid
        self.logdir = logdir

    def get_logger(self, name, filename):
        filepath = os.path.join(self.logdir, filename)
        if os.access(filepath, os.F_OK):
            os.remove(filepath)
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(logging.handlers.RotatingFileHandler(filepath, maxBytes=300000, backupCount=2))
        return logger

    def get_url_info(self, url):
        """Return a (code, content_length) tuple from making an
           HTTP HEAD request for the given url.
        """

        try:
            content_length = -1
            p = urlparse(url)

            conn = httplib.HTTPConnection(p[1])
            conn.request('HEAD', p[2])
            res = conn.getresponse()
            code = res.status

            if code == 200:
                for header in res.getheaders():
                    if header[0] == 'content-length':
                        content_length = int(header[1])

            return (code, content_length)

        except AttributeError:
            # this can happen when we didn't get a valid url from pulse
            return (-1, -1)

        except Exception, inst:
            # XXX: something bad happened; we should log this
            # return (-1, -1)
            raise

    def process_builddata(self, data):
        if not data.get('logurl'):
            # should log this
            return

        # If it's been less than 15s since we checked for this particular
        # log, put this item back in the queue without checking again.
        now = calendar.timegm(time.gmtime())
        last_check = data.get('last_check', 0)
        if last_check and now - last_check < 15:
            self.queue.put(data)
            return

        code, content_length = self.get_url_info(str(data['logurl']))
        if DEBUG:
            if data.get('last_check'):
                print '...reprocessing logfile', code, data.get('logurl')
                print '...', data.get('key')
                print '...', now - data.get('insertion_time', 0), 'seconds since insertion_time'
            else:
                print 'processing logfile', code, data.get('logurl')
        if code == 200:
            self.publish_unittest_message(data)
        else:
            if now - data.get('insertion_time', 0) > 600:
                # Currently, this is raised for unittests from beta and aurora
                # builds at least, as their log files get stored in a place
                # entirely different than the builds.  This should change soon
                # per bug 713846, so I've not adapted the code to handle this.
                raise LogTimeoutError(data.get('key', 'unknown'), data.get('logurl'))
            else:
                # re-insert this into the queue
                data['last_check'] = now
                if DEBUG:
                    print 'requeueing after check'
                self.queue.put(data)

    def publish_unittest_message(self, data):
        # The original routing key has the format build.foo.bar.finished;
        # we only use 'foo' in the new routing key.
        original_key = data['key'].split('.')[1]
        tree = data['tree']
        platform = data['platform']
        buildtype = data['buildtype']
        os = data['os']
        test = data['test']
        product = data['product'] if data['product'] else 'unknown'
        key_parts = ['talos' if data['talos'] else 'unittest',
                     tree,
                     platform,
                     os,
                     buildtype,
                     test,
                     product,
                     original_key]

        publish_message(TranlsatorPublisher, data, '.'.join(key_parts))

    def start(self):
        self.errorLogger = self.get_logger('LogHandlerErrorLog', 'log_handler_error.log')
        while True:
            try:
                data = None

                # Check if the parent process is still alive, and if so,
                # look for another log to process.
                if 'windows' in platform.system().lower():
                    proc = subprocess.Popen(['tasklist', '-FI', 'PID eq %d' % self.parent_pid],
                                            stderr=subprocess.STDOUT,
                                            stdout=subprocess.PIPE)
                    if not proc.wait():
                        result = proc.stdout.read()
                        if not str(self.parent_pid) in result:
                            raise OSError
                    else:
                        raise Exception("Unable to call tasklist")
                else:
                    os.kill(self.parent_pid, 0)
                data = self.queue.get_nowait()
                self.process_builddata(data)
            except Empty:
                time.sleep(5)
                continue
            except OSError:
                # if the parent process isn't alive, shutdown gracefully
                # XXX: Need to drain the queue to a file before shutting
                # down, so we can pick up where we left off when we resume.
                sys.exit(0)
            except Exception, inst:
                obj_to_log = data
                if data.get('payload') and data['payload'].get('build') and data['payload']['build'].get('properties'):
                    obj_to_log = data['payload']['build']['properties']
                self.errorLogger.exception(json.dumps(obj_to_log, indent=2))
