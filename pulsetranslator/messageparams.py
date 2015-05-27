# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import re


buildtypes = [ 'opt', 'debug', 'pgo' ]

def guess_platform(builder):
    for platform in sorted(platforms.keys(), reverse=True):
        if platform in builder:
            return platform

    for key in platforms:
        for os in platforms[key]:
            if os in builder:
                return os

def convert_os(data):
    if re.search(r'OS\s*X\s*10.5', data['buildername'], re.I):
        return 'leopard'
    if re.search(r'OS\s*X\s*10.6', data['buildername'], re.I):
        return 'snowleopard'
    if re.search(r'OS\s*X\s*10.7', data['buildername'], re.I):
        return 'lion'
    if re.search(r'OS\s*X\s*10.8', data['buildername'], re.I):
        return 'mountainlion'
    if re.search(r'WINNT\s*5.2', data['buildername'], re.I):
        return 'xp'
    return 'unknown'

os_conversions = {
    'leopard-o': lambda x: 'leopard',
    'tegra_android-o': lambda x: 'tegra_android',
    'macosx': convert_os,
    'macosx64': convert_os,
    'win32': convert_os,
}

platforms = {
    'emulator': ['emulator', 'ubuntu64_vm-b2g-emulator'],
    'emulator-kk': ['emulator-kk'],
    'emulator-jb': ['emulator-jb'],
    'linux64-asan': ['linux64-asan', 'ubuntu64-asan_vm'],
    'linux32_gecko': ['linux32_gecko', 'ubuntu32_vm-b2gdt'],
    'linux64_gecko': ['linux64_gecko', 'ubuntu64_vm-b2gdt'],
    'linux64-rpm': ['fedora64'],
    'linux64': ['fedora64', 'ubuntu64', 'ubuntu64_hw', 'ubuntu64_vm'],
    'linux64-mulet': ['linux64-mulet', 'ubuntu64_vm-mulet'],
    'linuxqt': ['fedora'],
    'linux-rpm': ['fedora'],
    'linux': ['fedora', 'linux', 'ubuntu32', 'ubuntu32_vm', 'ubuntu32_hw'],
    'win32': ['xp', 'win7', 'win8', 'win7-ix', 'xp-ix'],
    'win32_gecko': ['win32_gecko'],
    'win32-mulet': ['win32-mulet'],
    'win64': ['w764', 'win8_64'],
    'macosx64': ['macosx64', 'snowleopard', 'leopard', 'lion', 'mountainlion', 'yosemite'],
    'macosx64_gecko': ['macosx64_gecko', 'mountainlion-b2gdt'],
    'macosx64-mulet': ['macosx64-mulet'],
    'macosx': ['macosx', 'leopard'],
    'android-armv6': ['ubuntu64_vm_armv6_mobile', 'ubuntu64_vm_armv6_large'],
    'android-x86': ['android-x86', 'ubuntu64_hw'],
    'android': ['panda_android', 'ubuntu64_vm_mobile', 'ubuntu64_vm_large'],
    'android-api-9': ['ubuntu64_vm_mobile', 'ubuntu64_vm_large'],
    'android-api-10': ['panda_android'],
    'android-api-11': ['panda_android', 'ubuntu64_vm_armv7_large', 'ubuntu64_vm_armv7_mobile'],
    'ics_armv7a_gecko': ['ubuntu64-b2g'],
}

tags = [
        '',
        'build',
        'dep',
        'dtrace',
        'l10n',
        'nightly',
        'nomethodjit',
        'notracejit',
        'release',
        'shark',
        'spidermonkey',
        'valgrind',
        'warnaserr',
        'warnaserrdebug',
        'xulrunner',
       ]
