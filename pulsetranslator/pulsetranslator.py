# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import calendar
import datetime
from dateutil.parser import parse
import json
import logging
import logging.handlers
from mozillapulse import consumers
from multiprocessing import Process, Queue
import os
import re
import socket
import time

from translatorexceptions import *
from loghandler import LogHandler
import messageparams
from translatorqueues import *


class PulseBuildbotTranslator(object):

    def __init__(self, logdir='logs'):
        self.label = 'pulse-build-translator-%s' % socket.gethostname()
        self.pulse = consumers.BuildConsumer(applabel=self.label)
        self.pulse.configure(topic=['#.finished', '#.log_uploaded'],
                             callback=self.on_pulse_message,
                             durable=False)
        self.queue = Queue()
        self.logdir = logdir

        if not os.access(self.logdir, os.F_OK):
            os.mkdir(self.logdir)

        self.badPulseMessageLogger = self.get_logger('BadPulseMessage', 'bad_pulse_message.log')
        self.errorLogger = self.get_logger('ErrorLog', 'error.log')

    def get_logger(self, name, filename):
        filepath = os.path.join(self.logdir, filename)
        if os.access(filepath, os.F_OK):
            os.remove(filepath)
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(logging.handlers.RotatingFileHandler(filepath, maxBytes=300000, backupCount=2))
        return logger

    def start(self):
        loghandler = LogHandler(self.queue, os.getpid(), self.logdir)
        self.logprocess = Process(target=loghandler.start)
        self.logprocess.start()
        self.pulse.listen()

    def buildid2date(self, string):
        """Takes a buildid string and returns a python datetime and 
           seconds since epoch.
        """

        date = parse(string)
        return (date, int(time.mktime(date.timetuple())))

    def process_unittest(self, data):
        data['insertion_time'] = calendar.timegm(time.gmtime())
        if not data.get('logurl'):
            raise NoLogUrlError(data['key'])
        if data['platform'] not in messageparams.platforms:
            raise BadPlatformError(data['key'], data['platform'])
        elif data['os'] not in messageparams.platforms[data['platform']]:
            raise BadOSError(data['key'], data['platform'], data['os'], data['buildername'])
        else:
            self.queue.put(data)

    def process_build(self, data):
        if data['platform'] not in messageparams.platforms:
            raise BadPlatformError(data['key'], data['platform'])
        for tag in data['tags']:
            if tag not in messageparams.tags:
                raise BadTagError(data['key'], tag, data['platform'], data['product'])
        if not data['buildurl']:
            raise NoBuildUrlError(data['key'])
        self.publish_build_message(data)

    def publish_build_message(self, data):
        # The original routing key has the format build.foo.bar.finished;
        # we only use 'foo' in the new routing key.
        original_key = data['key'].split('.')[1]
        tree = data['tree']
        platform = data['platform']
        buildtype = data['buildtype']
        key_parts = ['build', tree, platform, buildtype]
        for tag in data['tags']:
            if tag:
                key_parts.append(tag)
        key_parts.append(original_key)

        publish_message(TranlsatorPublisher, data, '.'.join(key_parts))

    def on_pulse_message(self, data, message):
        key = 'unknown'
        stage_platform = None

        try:
            key = data['_meta']['routing_key']

            # Acknowledge the message so it doesn't hang around on the
            # pulse server.
            message.ack()

            # Create a dict that holds build properties that apply to both
            # unittests and builds.
            builddata = { 'key': key,
                          'buildid': None,
                          'platform': None,
                          'builddate': None,
                          'buildurl': None,
                          'logurl': None,
                          'testsurl': None,
                          'release': None,
                          'buildername': None,
                          'revision': None,
                          'product': None,
                          'tree': None,
                          'timestamp': datetime.datetime.now().strftime('%Y%m%d%H%M%S'),
                        }

            # scan the payload for properties applicable to both tests and builds
            for property in data['payload']['build']['properties']:

                # look for revision
                if property[0] == 'revision':
                    builddata['revision'] = property[1]

                # look for product
                if property[0] == 'product':
                    builddata['product'] = property[1]

                # look for tree
                if property[0] == 'branch':
                    builddata['tree'] = property[1]
                    # For builds, this proeprty is sometimes a relative path,
                    # ('releases/mozilla-beta') and not just a name.  For
                    # consistency, we'll strip the path components.
                    if isinstance(builddata['tree'], basestring):
                        builddata['tree'] = os.path.basename(builddata['tree'])

                # look for buildid
                if property[0] == 'buildid':
                    builddata['buildid'] = property[1]
                    date, builddata['builddate'] = self.buildid2date(property[1])

                # look for platform
                elif property[0] == 'platform':
                    builddata['platform'] = property[1]
                    if '-debug' in builddata['platform']:
                        # strip '-debug' from the platform string if it's present
                        builddata['platform'] = builddata['platform'][0:builddata['platform'].find('-debug')]

                # look for build url
                elif property[0] in ['packageUrl', 'build_url', 'fileURL']:
                    builddata['buildurl'] = property[1]

                # look for log url
                elif property[0] == 'log_url':
                    builddata['logurl'] = property[1]

                # look for release name
                elif property[0] in ['en_revision', 'script_repo_revision']:
                    builddata['release'] = property[1]

                # look for tests url
                elif property[0] == 'testsUrl':
                    builddata['testsurl'] = property[1]

                # look for buildername
                elif property[0] == 'buildername':
                    builddata['buildername'] = property[1]

                # look for stage_platform
                elif property[0] == 'stage_platform':
                    # For some messages, the platform we really care about
                    # is in the 'stage_platform' property, not the 'platform'
                    # property.
                    stage_platform = property[1]
                    for type in messageparams.buildtypes:
                        if type in stage_platform:
                            stage_platform = stage_platform[0:stage_platform.find(type) - 1]

            if not builddata['tree']:
                raise BadPulseMessageError(key, "no 'branch' property")

            builddata['buildtype'] = 'opt'
            if 'debug' in key:
                builddata['buildtype'] = 'debug'
            elif 'pgo' in key:
                builddata['buildtype'] = 'pgo'

            # see if this message is for a unittest
            unittestRe = re.compile(r'build\.((%s)[-|_](.*?)(-debug|-o-debug|-pgo|_pgo|_test)?[-|_](test|unittest|pgo)-(.*?))\.(\d+)\.(log_uploaded|finished)' %
                                    builddata['tree'])
            match = unittestRe.match(key)
            if match:
                # for unittests, generate some metadata by parsing the key

                if match.groups()[7] == 'finished':
                    # Ignore this message, we only care about 'log_uploaded'
                    # messages for unittests.
                    return

                # The 'short_builder' string is quite arbitrary, and so this
                # code is expected to be fragile, and will likely need
                # frequent maintenance to deal with future changes to this
                # string.  Unfortunately, these items are not available
                # in a more straightforward fashion at present.
                short_builder = match.groups()[0]

                builddata['os'] = match.groups()[2]
                if builddata['os'] in messageparams.os_conversions:
                    builddata['os'] = messageparams.os_conversions[builddata['os']](builddata)

                builddata['test'] = match.groups()[5]

                # yuck!!
                if builddata['test'].endswith('_2'):
                    short_builder = "%s.2" % short_builder[0:-2]
                elif builddata['test'].endswith('_2-pgo'):
                    short_builder = "%s.2-pgo" % short_builder[0:-6]

                builddata['buildnumber'] = match.groups()[6]
                builddata['talos'] = 'talos' in builddata['buildername']
 
                if stage_platform:
                    builddata['platform'] = stage_platform

                self.process_unittest(builddata)
            elif 'source' in key:
                # what is this?
                # ex: build.release-mozilla-esr10-firefox_source.0.finished
                pass
            elif 'repack' in key:
                # what is this?
                # ex: build.release-mozilla-beta-linux_repack_1.45.finished
                pass
            elif [x for x in ['schedulers', 'tag', 'submitter', 'final_verification'] if x in key]:
                # internal buildbot stuff we don't care about
                # ex: build.release-mozilla-beta-firefox_reset_schedulers.12.finished
                # ex: build.release-mozilla-beta-fennec_tag.40.finished
                # ex: build.release-mozilla-beta-bouncer_submitter.46.finished
                pass
            elif 'jetpack' in key:
                # These are very awkwardly formed; i.e.
                # build.jetpack-mozilla-central-win7-debug.18.finished,
                # and the tree appears nowhere except this string.  In order
                # to support these we'd have to keep a tree map of all
                # possible trees.
                pass
            else:
                if not builddata['platform']:
                    if stage_platform:
                        builddata['platform'] = stage_platform
                    else:
                        # Some messages don't contain the platform
                        # in any place other than the routing key, so we'll
                        # have to guess it based on that.
                        builddata['platform'] = messageparams.guess_platform(key)
                        if not builddata['platform']:
                            raise BadPulseMessageError(key, 'no "platform" property')
                otherRe = re.compile(r'build\.((release-|jetpack-)?(%s)[-|_](xulrunner[-|_])?(%s)([-|_]?)(.*?))\.(\d+)\.(log_uploaded|finished)' %
                                     (builddata['tree'], builddata['platform']))
                match = otherRe.match(key)
                if match:
                    if 'log_uploaded' in match.group(9):
                        # we only care about 'finished' message for builds
                        return

                    builddata['tags'] = match.group(7).replace('_', '-').split('-')

                    # There are some tags we don't care about as tags,
                    # usually because they are redundant with other properties,
                    # so remove them.
                    notags = ['debug', 'pgo', 'opt']
                    builddata['tags'] = [x for x in builddata['tags'] if x not in notags]

                    # Sometimes a tag will just be a digit, i.e.,
                    # build.mozilla-central-android-l10n_5.12.finished;
                    # strip these.
                    builddata['tags'] = [x for x in builddata['tags'] if not x.isdigit()]

                    if isinstance(match.group(2), basestring):
                        if 'release' in match.group(2):
                            builddata['tags'].append('release')
                        if 'jetpack' in match.group(2):
                            builddata['tags'].append('jetpack')

                    if match.group(4) or 'xulrunner' in builddata['tags']:
                        builddata['product'] = 'xulrunner'

                    self.process_build(builddata)
                else:
                    raise BadPulseMessageError(key, "unknown message type")

        except BadPulseMessageError, inst:
            self.badPulseMessageLogger.exception(json.dumps(data.get('payload'), indent=2))
        except Exception, inst:
            self.errorLogger.exception(json.dumps(data, indent=2))
