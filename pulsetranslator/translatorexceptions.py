# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

class BadPulseMessageError(Exception):

    def __init__(self, key, error):
        self.key = key
        self.error = error

    def __str__(self):
        return "%s, key: %s" % (self.error, self.key)

class NoLogUrlError(BadPulseMessageError):

    def __init__(self, key):
        self.key = key

    def __str__(self):
        return self.key

class NoBuildUrlError(BadPulseMessageError):

    def __init__(self, key):
        self.key = key

    def __str__(self):
        return self.key

class BadTagError(BadPulseMessageError):

    def __init__(self, key, tag, platform, product):
        self.key = key
        self.tag = tag
        self.platform = platform
        self.product = product

    def __str__(self):
        return ("%s, tag: %s, platform: %s, product: %s" %
            (self.key, self.tag, self.platform, self.product))

class BadPlatformError(BadPulseMessageError):

    def __init__(self, key, platform):
        self.key = key
        self.platform = platform

    def __str__(self):
        return "%s, platform: %s" % (self.key, self.platform)

class BadOSError(BadPlatformError):

    def __init__(self, key, platform, os, buildername):
        self.key = key
        self.platform = platform
        self.os = os
        self.buildername = buildername

    def __str__(self):
        return ("%s, platform: %s, os: %s, builder: %s" %
            (self.key, self.platform, self.os, self.buildername))

class LogTimeoutError(Exception):

    def __init__(self, key, logurl):
        self.key = key
        self.logurl = logurl

    def __str__(self):
        return "key: %s, url: %s" % (self.key, self.logurl)
