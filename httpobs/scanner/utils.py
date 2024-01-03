import json
import os.path
import sys

import requests
from bs4 import BeautifulSoup as bs
from requests.structures import CaseInsensitiveDict

from httpobs.conf import SCANNER_PINNED_DOMAINS

HSTS_URL = 'https://raw.githubusercontent.com/chromium/chromium/main/net/http/transport_security_state_static.json'


def parse_http_equiv_headers(html: str) -> CaseInsensitiveDict:
    http_equiv_headers = CaseInsensitiveDict(
        {
            'Content-Security-Policy': [],
        }
    )

    # Try to parse the HTML
    try:
        soup = bs(html, 'html.parser')
    except:
        return http_equiv_headers

    # Find all the meta tags
    metas = soup.find_all('meta')

    for meta in metas:
        if meta.has_attr('http-equiv') and meta.has_attr('content'):
            # Add support for multiple CSP policies specified via http-equiv
            # See issue: https://github.com/mozilla/http-observatory/issues/266
            # Note that this is so far only done for CSP and not for other types
            # of http-equiv
            if meta.get('http-equiv', '').lower().strip() == 'content-security-policy':
                http_equiv_headers['Content-Security-Policy'].append(meta.get('content'))

        # Technically not HTTP Equiv, but I'm treating it that way
        elif meta.get('name', '').lower().strip() == 'referrer' and meta.has_attr('content'):
            http_equiv_headers['Referrer-Policy'] = meta.get('content')

    return http_equiv_headers


def retrieve_store_hsts_preload_list():
    # Download the Google HSTS Preload List
    try:
        r = requests.get(HSTS_URL).text.split('\n')

        # Remove all the comments
        r = ''.join([line.split('// ')[0] for line in r if line.strip() != '//'])

        r = json.loads(r)

        # Mapping of site -> whether it includes subdomains
        hsts = {
            site['name']: {
                'includeSubDomains': site.get('include_subdomains', False),
                'includeSubDomainsForPinning': site.get('include_subdomains', False)
                or site.get('include_subdomains_for_pinning', False),
                'mode': site.get('mode'),
                'pinned': True if 'pins' in site else False,
            }
            for site in r['entries']
        }

        # Add in the manually pinned domains
        for pinned_domain in SCANNER_PINNED_DOMAINS:
            hsts[pinned_domain] = {
                'includeSubDomains': True,
                'includeSubDomainsForPinning': True,
                'mode': 'force-https',
                'pinned': True,
            }

        # Write json file to disk
        __dirname = os.path.abspath(os.path.dirname(__file__))
        __filename = os.path.join(__dirname, '..', 'conf', 'hsts-preload.json')

        with open(__filename, 'w') as f:
            json.dump(hsts, f, indent=2, sort_keys=True)

    except:
        print('Unable to download the Chromium HSTS preload list.', file=sys.stderr)


def sanitize_headers(headers: dict) -> dict:
    """
    :param headers: raw headers object from a request's response
    :return: that same header, after sanitization
    """
    try:
        if len(str(headers)) <= 16384:
            return dict(headers)
        else:
            return None

    except:
        return None


# allow for this file to be run directly to fetch the HSTS preload list via the debugger
# or via the regen script
if __name__ == "__main__":
    retrieve_store_hsts_preload_list()
