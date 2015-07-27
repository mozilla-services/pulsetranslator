# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import calendar
import copy
import datetime
import json
import logging
import logging.handlers
import os
import re
import socket
import time

from dateutil.parser import parse
from mozillapulse import consumers

import messageparams

from loghandler import LogHandler
from translatorexceptions import (BadLocalesError, BadOSError,
                                  BadPlatformError, BadPulseMessageError,
                                  BadTagError, NoBuildUrlError, NoLogUrlError)


class PulseBuildbotTranslator(object):

    def __init__(self, durable=False, logdir='logs', message=None,
                 display_only=False, consumer_cfg=None, publisher_cfg=None,
                 label=None):
        self.durable = durable
        self.label = 'pulse-build-translator-%s' % (label or
                                                    socket.gethostname())
        self.logdir = logdir
        self.message = message
        self.display_only = display_only
        self.consumer_cfg = consumer_cfg
        self.publisher_cfg = publisher_cfg

        if not os.access(self.logdir, os.F_OK):
            os.mkdir(self.logdir)

        self.bad_pulse_msg_logger = self.get_logger('BadPulseMessage',
                                                    'bad_pulse_message.log')

        self.error_logger = self.get_logger('ErrorLog',
                                            'error.log',
                                            stderr=True)

        loghandler_error_logger = self.get_logger('LogHandlerErrorLog',
                                                  'log_handler_error.log',
                                                  stderr=True)
        self.loghandler = LogHandler(loghandler_error_logger,
                                     self.publisher_cfg)

    def get_logger(self, name, filename, stderr=False):
        filepath = os.path.join(self.logdir, filename)
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        handler = logging.handlers.RotatingFileHandler(
            filepath, mode='a+', maxBytes=300000, backupCount=2)
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s: %(message)s", "%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        if stderr:
            handler = logging.StreamHandler()
            logger.addHandler(handler)

        return logger

    def start(self):
        if self.message:
            # handle a test message
            json_data = open(self.message)
            data = json.load(json_data)
            self.on_pulse_message(data)
            return

        # Start listening for pulse messages. If 5 failures in a
        # minute, wait 5 minutes before retrying.
        failures = []
        while True:
            pulse = consumers.BuildConsumer(applabel=self.label, connect=False)
            pulse.configure(topic=['#.finished', '#.log_uploaded'],
                            callback=self.on_pulse_message,
                            durable=self.durable)
            if self.consumer_cfg:
                pulse.config = self.consumer_cfg

            try:
                pulse.listen()
            except Exception:
                self.error_logger.exception(
                    "Error occurred during pulse.listen()")

            now = datetime.datetime.now()
            failures = [x for x in failures
                        if now - x < datetime.timedelta(seconds=60)]
            failures.append(now)
            if len(failures) >= 5:
                failures = []
                time.sleep(5 * 60)

    def buildid2date(self, string):
        """Takes a buildid string and returns a python datetime and
           seconds since epoch.
        """

        date = parse(string)
        return (date, int(time.mktime(date.timetuple())))

    def process_unittest(self, data):
        data['insertion_time'] = calendar.timegm(time.gmtime())
        if data['platform'] in messageparams.ignored_platforms:
            return
        if not data.get('logurl'):
            raise NoLogUrlError(data['key'])
        if data['platform'] not in messageparams.platforms:
            raise BadPlatformError(data['key'], data['platform'])
        elif data['os'] not in messageparams.platforms[data['platform']]:
            raise BadOSError(data['key'], data['platform'], data['os'],
                             data['buildername'])

        if self.display_only:
            print "Test properties:\n%s\n" % json.dumps(data)
            return

        self.loghandler.handle_message(data)

    def process_build(self, data):
        if data['platform'] in messageparams.ignored_platforms:
            return
        if data['platform'] not in messageparams.platforms:
            raise BadPlatformError(data['key'], data['platform'])
        for tag in data['tags']:
            if tag not in messageparams.tags:
                raise BadTagError(data['key'], tag, data['platform'],
                                  data['product'])
        # Repacks do not have a buildurl included. We can remove this
        # workaround once bug 857971 has been fixed
        if not data['buildurl'] and not data['repack']:
            raise NoBuildUrlError(data['key'])

        if self.display_only:
            print "Build properties:\n%s\n" % json.dumps(data)
            return

        self.loghandler.handle_message(data)

    def on_pulse_message(self, data, message=None):
        key = 'unknown'
        stage_platform = None

        try:
            key = data['_meta']['routing_key']

            # Acknowledge the message so it doesn't hang around on the
            # pulse server.
            if message:
                message.ack()

            # Create a dict that holds build properties that apply to both
            # unittests and builds.
            builddata = { 'key': key,
                          'job_number': None,
                          'buildid': None,
                          'build_number': None,
                          'previous_buildid': None,
                          'status': None,
                          'platform': None,
                          'builddate': None,
                          'buildurl': None,
                          'locale': None,
                          'locales': None,
                          'logurl': None,
                          'testsurl': None,
                          'test_packages_url': None,
                          'release': None,
                          'buildername': None,
                          'slave': None,
                          'repack': None,
                          'revision': None,
                          'product': None,
                          'version': None,
                          'tree': None,
                          'timestamp': datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                        }

            # scan the payload for properties applicable to both tests and
            # builds
            for prop in data['payload']['build']['properties']:

                # look for the job number
                if prop[0] == 'buildnumber':
                    builddata['job_number'] = prop[1]

                # look for revision
                if prop[0] == 'revision':
                    builddata['revision'] = prop[1]

                # look for product
                elif prop[0] == 'product':
                    # Bug 1010120:
                    # Ensure to lowercase to prevent issues with capitalization
                    builddata['product'] = prop[1].lower()

                # look for version
                elif prop[0] == 'version':
                    builddata['version'] = prop[1]

                # look for tree
                elif prop[0] == 'branch':
                    builddata['tree'] = prop[1]
                    # For builds, this property is sometimes a relative path,
                    # ('releases/mozilla-beta') and not just a name.  For
                    # consistency, we'll strip the path components.
                    if isinstance(builddata['tree'], basestring):
                        builddata['tree'] = os.path.basename(builddata['tree'])

                # look for buildid
                elif prop[0] == 'buildid':
                    builddata['buildid'] = prop[1]
                    date, builddata['builddate'] = self.buildid2date(prop[1])

                # look for the build number which comes with candidate builds
                elif prop[0] == 'build_number':
                    builddata['build_number'] = prop[1]

                # look for the previous buildid
                elif prop[0] == 'previous_buildid':
                    builddata['previous_buildid'] = prop[1]

                # look for platform
                elif prop[0] == 'platform':
                    builddata['platform'] = prop[1]
                    if (builddata['platform'] and
                        '-debug' in builddata['platform']):
                        # strip '-debug' from the platform string if it's
                        # present
                        builddata['platform'] = builddata['platform'][
                            0:builddata['platform'].find('-debug')]

                # look for the locale
                elif prop[0] == 'locale':
                    builddata['locale'] = prop[1]

                # look for the locale
                elif prop[0] == 'locales':
                    builddata['locales'] = prop[1]

                # look for build url
                elif prop[0] in ['packageUrl', 'build_url', 'fileURL']:
                    builddata['buildurl'] = prop[1]

                # look for log url
                elif prop[0] == 'log_url':
                    builddata['logurl'] = prop[1]

                # look for release name
                elif prop[0] in ['en_revision', 'script_repo_revision']:
                    builddata['release'] = prop[1]

                # look for tests url
                elif prop[0] == 'testsUrl':
                    builddata['testsurl'] = prop[1]

                # look for url to json manifest of test packages
                elif prop[0] == 'testPackagesUrl':
                    builddata['test_packages_url'] = prop[1]

                # look for buildername
                elif prop[0] == 'buildername':
                    builddata['buildername'] = prop[1]

                # look for slave builder
                elif prop[0] == 'slavename':
                    builddata['slave'] = prop[1]

                # look for blobber files
                elif prop[0] == 'blobber_files':
                    try:
                        builddata['blobber_files'] = json.loads(prop[1])
                    except ValueError:
                        self.error_logger.exception(
                            "Malformed `blobber_files` buildbot property: {}".format(prop[1]))

                # look for stage_platform
                elif prop[0] == 'stage_platform':
                    # For some messages, the platform we really care about
                    # is in the 'stage_platform' property, not the 'platform'
                    # property.
                    stage_platform = prop[1]
                    for buildtype in messageparams.buildtypes:
                        if buildtype in stage_platform:
                            stage_platform = stage_platform[0:stage_platform.find(buildtype) - 1]

                elif prop[0] == 'completeMarUrl':
                    builddata['completemarurl'] = prop[1]

                elif prop[0] == 'completeMarHash':
                    builddata['completemarhash'] = prop[1]

            if not builddata['tree']:
                raise BadPulseMessageError(key, "no 'branch' property")

            # If no locale is given fallback to en-US
            if not builddata['locale']:
                builddata['locale'] = 'en-US'

            # status of the build or test notification
            # see http://hg.mozilla.org/build/buildbot/file/08b7c51d2962/master/buildbot/status/builder.py#l25
            builddata['status'] = data['payload']['build']['results']

            if 'debug' in key:
                builddata['buildtype'] = 'debug'
            elif 'pgo' in key:
                builddata['buildtype'] = 'pgo'
            else:
                builddata['buildtype'] = 'opt'

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
                    builddata['os'] = messageparams.os_conversions[
                        builddata['os']](builddata)

                builddata['test'] = match.groups()[5]

                # yuck!!
                if builddata['test'].endswith('_2'):
                    short_builder = "%s.2" % short_builder[0:-2]
                elif builddata['test'].endswith('_2-pgo'):
                    short_builder = "%s.2-pgo" % short_builder[0:-6]

                builddata['talos'] = 'talos' in builddata['buildername']

                if stage_platform:
                    builddata['platform'] = stage_platform

                self.process_unittest(builddata)
            elif 'source' in key:
                # what is this?
                # ex: build.release-mozilla-esr10-firefox_source.0.finished
                pass
            elif [x for x in ['schedulers', 'tag', 'submitter', 'final_verification', 'fuzzer'] if x in key]:
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

                otherRe = re.compile(r'build\.((release-|jetpack-|b2g_)?(%s)[-|_](xulrunner[-|_])?(%s)([-|_]?)(.*?))\.(\d+)\.(log_uploaded|finished)' %
                                     (builddata['tree'], builddata['platform']))
                match = otherRe.match(key)
                if match:
                    if 'finished' in match.group(9):
                        # Ignore this message, we only care about 'log_uploaded'
                        # messages for builds
                        return

                    builddata['tags'] = match.group(7).replace('_', '-').split('-')

                    # There are some tags we don't care about as tags,
                    # usually because they are redundant with other properties,
                    # so remove them.
                    notags = ['debug', 'pgo', 'opt', 'repack']
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

                    # Sadly, the build url for emulator builds isn't published
                    # to the pulse stream, so we have to guess it.  See bug
                    # 1071642.
                    if ('emulator' in builddata.get('platform', '') and
                            'try' not in key and builddata.get('buildid')):
                        builddata['buildurl'] = (
                            'https://pvtbuilds.mozilla.org/pub/mozilla.org/b2g/tinderbox-builds' +
                            '/%s-%s/%s/emulator.tar.gz' %
                            (builddata['tree'], builddata['platform'],
                             builddata['buildid']))

                    # In case of repacks we have to send multiple notifications,
                    # each for every locale included. We can remove this
                    # workaround once bug 857971 has been fixed.
                    if 'repack' in key:
                        builddata['repack'] = True

                        if not builddata["locales"]:
                            raise BadPulseMessageError(key, 'no "locales" property')

                        for locale in builddata["locales"].split(','):
                            if not locale:
                                raise BadLocalesError(key, builddata["locales"])

                            data = copy.deepcopy(builddata)
                            data['locale'] = locale
                            self.process_build(data)

                    else:
                        self.process_build(builddata)
                else:
                    raise BadPulseMessageError(key, "unknown message type, platform: %s" % builddata.get('platform', 'unknown'))

        except BadPulseMessageError as inst:
            self.bad_pulse_msg_logger.exception(json.dumps(data.get('payload'),
                                                           indent=2))
            print(inst.__class__, str(inst))
        except Exception:
            self.error_logger.exception(json.dumps(data, indent=2))
