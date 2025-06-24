"""A module for validating the API response structure from the CTA Train Locations API."""
import unittest
import requests
import os

class TestTrainLocationResponse(unittest.TestCase):
    """Class for testing API response from CTA API."""
    def test_cta_api_response_structure(self):
        """Tests the API response from the CTA Train Locations endpoint matches the expected structure."""
        base_url = 'https://lapi.transitchicago.com/api/1.0/ttpositions.aspx'
        query_params = {
            'rt': 'Blue',
            'key': os.environ['API_KEY'],
            'outputType': 'JSON'
        }

        response = requests.get(url=base_url, params=query_params)
        data = response.json()

        assert response.status_code == 200
        assert 'ctatt' in data
        assert 'route' in data['ctatt']
        assert isinstance(data['ctatt']['route'], list)
        assert 'train' in data['ctatt']['route'][0]
        assert isinstance(data['ctatt']['route'][0]['train'], list)
        for train in data['ctatt']['route'][0]['train']:
            assert 'rn' in train
            assert isinstance('rn', str)
            assert 'destNm' in train
            assert isinstance('destNm', str)
            assert 'nextStaNm' in train
            assert isinstance('nextStaNm', str)
            assert 'prdt' in train
            assert isinstance('prdt', str)
            assert 'arrT' in train
            assert isinstance('arrT', str)
            assert 'isApp' in train
            assert isinstance('isApp', str)
            assert 'isDly' in train
            assert isinstance('isDly', str)
