PulseTranslator
===============

The pulsetranslator script consumes Mozilla buildbot pulse messages
and then re-publishes them in a normalized format.  It does this
because native buildbot messages do not share any consistent
structure, and change frequently and without warning.  Consuming them
directly is therefore error-prone and subject to frequent failure.

The normalized messages are published to the exchange
"exchange/build/normalized".


Installing, Configuring, and Running
------------------------------------

Install pulsetranslator as any regular Python package:

    python setup.py install

You'll need to create a ini-style config file with information on the
Pulse accounts.  It should have both [publisher] and [consumer]
sections, and both must contain at least "user" and "password"
options.  They can also include any of the standard mozillapulse
[configuration options][].

The minimum command line to run pulsetranslator is

    runtranslator --pulse-cfg=<path to config file>

You can get help on other options by running

    runtranslator -h


Routing Keys
------------

For unittests:

    unittest.%tree%.%platform%.%os%.%buildtype%.%testname%.%product%.%builder%

For example,

    unittest.mozilla-central.win32.xp.debug.xpcshell.firefox.mozilla-central_xp-debug_test-xpcshell

For talos tests, the same format applies, except that the first part
of the key is 'talos' instead of 'unittest'.  For example:

    talos.try.linux64.fedora64.opt.chrome_2.firefox.try_fedora64_test-chrome

For builds:

    build.%tree%.%platform%.%buildtype%.%builder%

For example:

    build.try.android.debug.try-android-debug


Pulsebuildmonitor
-----------------

For simple uses, you may be able to consume messages directly from the
"exchange/build/normalized" exchange.  For more complex uses, you may
find it easier to use [pulsebuildmonitor][], which can filter messages
for you based on a number of criteria.  See the [pulsebuildmonitor README][]
for more details.

[configuration options]: https://hg.mozilla.org/automation/mozillapulse/file/tip/mozillapulse/config.py
[pulsebuildmonitor]: http://hg.mozilla.org/automation/pulsebuildmonitor
[pulsebuildmonitor README]: http://hg.mozilla.org/automation/pulsebuildmonitor/file/tip/README.txt
