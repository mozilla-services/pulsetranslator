# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
from setuptools import setup, find_packages

PACKAGE_NAME = 'pulsetranslator'
version = '0.1'

deps = ['mozillapulse']

python_version = sys.version_info[:2]
if python_version < (2,6) or python_version >= (3,0):
    print >>sys.stderr, '%s requires Python >= 2.6 and < 3.0' % PACKAGE_NAME
    sys.exit(1)

setup(name=PACKAGE_NAME,
      version=version,
      description=("Service for translating rawa buildbot pulse messages into "
                   "a standard format"),
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Jonathan Griffin',
      author_email='jgriffin@mozilla.com',
      url='http://hg.mozilla.org/users/jgriffin_mozilla.com/pulsetranslator',
      license='MPL',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=deps,
      entry_points="""
      # -*- Entry points: -*-
      [console_scripts]
      runtranslator = pulsetranslator.runservice:main
      """,
     )
