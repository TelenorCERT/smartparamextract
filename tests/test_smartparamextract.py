#!/usr/bin/env pytest
from __future__ import print_function, unicode_literals
import json
import os.path
import sys

import pytest
import requests_mock

TEST_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(TEST_DIR, '..'))

import smartparamextract

FOREMAN_CREDENTIALS = ('user', 'password')
FOREMAN_API = 'http://localhost/api'
FOREMAN_SC = FOREMAN_API + '/smart_class_parameters'

PAGE1_DATA = os.path.join(TEST_DIR, 'param_page1.json')
PAGE2_DATA = os.path.join(TEST_DIR, 'param_page2.json')

@pytest.fixture
def extractor():
    yield smartparamextract.SmartParamExtractor(FOREMAN_CREDENTIALS,
                                                FOREMAN_API)

@pytest.fixture
def all_params_mock():
    with open(PAGE1_DATA) as infile:
        page1 = infile.read()

    with open(PAGE2_DATA) as infile:
        page2 = infile.read()

    with requests_mock.mock() as mock:
        mock.get(FOREMAN_SC, [{'text': page1}, {'text': page2}])
        yield mock


def test_fetch_param_info(extractor):
    with requests_mock.mock() as mock:
        mock.get(FOREMAN_SC + '/1',
                text='{"status": "ok"}')
        result = extractor.fetch_param_info(1)

        assert mock.called
        assert result['status'] == 'ok'

def test_fetch_all_params(extractor, all_params_mock):
    result = extractor.fetch_all_params()

    assert all_params_mock.called
    assert all_params_mock.call_count == 2
    assert len(result) == 4
    assert all('required' in r for r in result)

def test_fetch_overridden_params(extractor, all_params_mock):
    result = extractor.fetch_overridden_params()

    assert all_params_mock.called
    assert all_params_mock.call_count == 2
    assert hasattr(result, 'next')
    assert len(list(result)) == 0

def test_fetch_all_param_info(extractor):
    def mock_callback(request, context):
        context.status_code = 200
        context.headers['Content-Type'] = 'application/json'
        return '{"bogus": true}'

    with open(PAGE1_DATA) as infile:
        page1 = infile.read()
        page1_data = json.loads(page1)
    with open(PAGE2_DATA) as infile:
        page2 = infile.read()
        page2_data = json.loads(page2)

    with requests_mock.mock() as mock:
        mock.get(FOREMAN_SC, [{'text': page1}, {'text': page2}])
        mock.get(FOREMAN_SC + '/', text=mock_callback)

        result = extractor.fetch_all_param_info()
        assert mock.called
