#!/usr/bin/env python
from __future__ import unicode_literals, print_function

from collections import Counter, OrderedDict
import json
import logging
import os
import os.path
import sys

import requests
import yaml
import pyaml


class SmartParamExtractor(object):

    def __init__(self, foreman_credentials, api_endpoint):
        self.session = requests.Session()
        self.session.auth = foreman_credentials
        self.session.headers.update({'Accept': 'application/json'})
        self.session.verify = False
        self.api = api_endpoint
        self.logger = logging.getLogger(__name__)
        self.string_style = None

        self.__all_params = []

    def fetch_all_params(self):
        if self.__all_params:
            return self.__all_params

        params = []

        response = self.session.get(self.api + '/smart_class_parameters').json()
        params.extend(response['results'])

        while len(params) < response['total']:
            search_params = {'page': response['page'] + 1}
            self.logger.info("Fetching page {}/{}".format(
                response['page'], response['total'] / response['per_page']))
            response = self.session.get(self.api + '/smart_class_parameters',
                                        params=search_params).json()
            params.extend(response['results'])

        self.__all_params = params
        return params

    def fetch_param_info(self, param_id):
        return self.session.get(
            self.api + '/smart_class_parameters/{id}'.format(id=param_id)).json()

    def fetch_overridden_params(self):
        return (
            self.fetch_param_info(p['id']) for p in
            self.fetch_all_params() if p['override_values_count'] > 0
        )

    def fetch_all_param_info(self):
        return (self.fetch_param_info(p['id']) for p in
                self.fetch_all_params())

    def fetch_merge_overrides(self):
        return sorted(
            p['puppetclass_name']['name'] + '::' + p['parameter'] for p in
            self.fetch_all_params() if p['merge_overrides']
        )

    def to_hiera(self):
        params = self.fetch_overridden_params()
        override_orders = Counter()

        for param in params:
            override_orders.update(
                [param['override_value_order'].replace('\r', '')]
            )

            if not param['override']:
                full_name = param['puppetclass_name']['name'] + \
                    '::' + param['parameter']
                self.logger.warn("%s has overrides configured, but is not " \
                                 "currently overridden in Foreman" % (full_name,))
            for override in param['override_values']:
                directory, filename = override['match'].split('=')
                yamlfile = os.path.join('hieradata/' + directory, filename + '.yaml')
                param_name = param['puppetclass_name']['name'] + '::' + \
                             param['parameter']

                self.__append_to_file(yamlfile, param_name, override['value'])

            if param['default_value']:
                self.__append_to_file('hieradata/common.yaml', param_name,
                                      param['default_value'])

        override_order = override_orders.most_common(1)[0][0]
        if len(override_orders) > 1:
            self.logger.warn(
                'Foreman uses more than one override order: %s' % (
                    override_orders.keys(),
            ))
            self.logger.warn('Choosing most common for hierarchy: %s' % (
                override_order,
            ))

        self.__create_hiera_yaml(override_order.split('\n'))
        self.__add_merge_overrides()

    def __add_merge_overrides(self):
        self.__append_to_file('hieradata/common.yaml', 'lookup_options',
                {k: {'merge': 'hash'} for k in self.fetch_merge_overrides()})

    def __append_to_file(self, filename, parameter, value):
        obj = {}

        if os.path.isfile(filename):
            with open(filename) as inputstream:
                try:
                    obj.update(yaml.safe_load(inputstream))
                except yaml.scanner.ScannerError:
                    print("Problem loading {}".format(filename),
                          file=sys.stderr)
                    print("Try running again with a different string style",
                          file=sys.stderr)
                    sys.exit(1)

        obj[parameter] = value

        directory = os.path.dirname(filename)
        if not os.path.isdir(directory):
            os.makedirs(directory)

        with open(filename, 'w') as outputstream:
            if self.string_style:
                pyaml.dump(obj, outputstream, vspacing=[1, 0],
                           string_val_style=self.string_style,
                           explicit_start=True)
            else:
                pyaml.dump(obj, outputstream, vspacing=[1, 0],
                           explicit_start=True)

    def __create_hiera_yaml(self, hierarchy):
        fact_mapping = {
            'fqdn': 'trusted.certname',
            'hostgroup': '::hostgroup',
            'os': 'facts.os.name',
            'domain': '::domainname',
        }

        hiera_config = OrderedDict((
            ('version', 5),
            ('defaults', {
                'datadir': 'hieradata',
                'data_hash': 'yaml_data',
            }),
            ('hierarchy', [])
        ))

        for elem in hierarchy:
            fact = fact_mapping.get(elem, 'FIXME:' + elem)

            hiera_config['hierarchy'].append({
                'name': 'Placeholder for {} data'.format(elem),
                'path': '{}/%{{{}}}.yaml'.format(elem, fact)
            })

        hiera_config['hierarchy'].append({
            'name': 'Common data',
            'path': 'hieradata/common.yaml',
        })

        with open('hiera.yaml', 'w') as outfile:
            pyaml.dump(hiera_config, outfile, vspacing=[1, 0],
                       explicit_start=True)

