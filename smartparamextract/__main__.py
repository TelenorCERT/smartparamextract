#!/usr/bin/env python
from __future__ import unicode_literals, print_function

import logging
import argparse
from collections import Counter
import os

import requests

from smartparamextract import SmartParamExtractor

requests.packages.urllib3.disable_warnings(
    requests.packages.urllib3.exceptions.InsecureRequestWarning
)

def foreman2hiera():
    _parser = argparse.ArgumentParser()

    _foreman = _parser.add_argument_group('Foreman parameters')
    _foreman.add_argument('-u', '--user', help='API user for Foreman',
            default=os.getenv('FOREMAN_USER', ''))
    _foreman.add_argument('-p', '--password', help='API password for Foreman',
            default=os.getenv('FOREMAN_PASSWORD', ''))
    _foreman.add_argument('-a', '--api', help='API endpoint for Foreman',
            default=os.getenv('FOREMAN_API', 'https://foreman/api'))

    _output = _parser.add_argument_group('Output options')
    _output.add_argument('-s', '--string-style',
                         choices=['"', '|', '>', 'plain'],
                         help='String style for YAML-output')
    _output.add_argument('-d', '--debug', action='store_const',
                         const=logging.DEBUG, dest='loglevel')
    _output.add_argument('-v', '--verbose', action='store_const',
                         const=logging.INFO, dest='loglevel')

    opts = _parser.parse_args()
    if not opts.loglevel:
        opts.loglevel = logging.WARN

    if not (opts.user and opts.password):
        _parser.error('Need username and password for Foreman API')

    logging.basicConfig(
        level=opts.loglevel,
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%H:%M:%S'
    )

    extractor = SmartParamExtractor((opts.user, opts.password), opts.api)
    if opts.string_style:
        extractor.string_style = opts.string_style
    extractor.to_hiera()


def remaining_params():
    _parser = argparse.ArgumentParser()

    _foreman = _parser.add_argument_group('Foreman parameters')
    _foreman.add_argument('-u', '--user', help='API user for Foreman',
            default=os.getenv('FOREMAN_USER', ''))
    _foreman.add_argument('-p', '--password', help='API password for Foreman',
            default=os.getenv('FOREMAN_PASSWORD', ''))
    _foreman.add_argument('-a', '--api', help='API endpoint for Foreman',
            default=os.getenv('FOREMAN_API', 'https://foreman/api'))
    opts = _parser.parse_args()

    if not (opts.user and opts.password):
        _parser.error('Need username and password for Foreman API')

    extractor = SmartParamExtractor((opts.user, opts.password), opts.api)
    overridden = [p for p in extractor.fetch_overridden_params() if p['override']]

    print("There are {} overridden parameters in Foreman".format(len(overridden)))
    print("")
    print("The involved classes are:")

    counts = Counter(p['puppetclass']['module_name'] for p in overridden)

    for klass, count in counts.most_common():
        print("{:3}: {}".format(count, klass))

if __name__ == '__main__':
    foreman2hiera()
