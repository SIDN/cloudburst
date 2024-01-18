#!/usr/bin/env python3
import requests
import functools
import sys
import subprocess
import json
import toml
from itertools import zip_longest

def google_json_parser(document):
    try:
        j = json.loads('\n'.join(document))
        prefixes4 = [v for p in j['prefixes'] for k,v in p.items() if k == "ipv4Prefix"]
        prefixes6 = [v for p in j['prefixes'] for k,v in p.items() if k == "ipv6Prefix"]
        return [*prefixes4, *prefixes6]
    except Exception as e:
        raise e
    return []

def fastly_json_parser(document):
    try:
        j = json.loads('\n'.join(document))
        prefixes4 = [a for a in j['addresses']]
        prefixes6 = [a for a in j['ipv6_addresses']]
        return [*prefixes4, *prefixes6]
    except Exception as e:
        raise e
    return []

def aws_json_parser(document):
    try:
        j = json.loads('\n'.join(document))
        prefixes4 = [v for p in j['prefixes'] for k,v in p.items() if k == "ip_prefix"]
        prefixes6 = [v for p in j['ipv6_prefixes'] for k,v in p.items() if k == "ipv6_prefix"]
        return [*prefixes4, *prefixes6]
    except Exception as e:
        raise e
    return []


def azure_json_parser(document):
    try:
        j = json.loads('\n'.join(document))
        prefixes = [p for st in j['values'] for p in st['properties']['addressPrefixes']]
        return prefixes
    except Exception as e:
        raise e
    return []

def o356_json_parser(document, service_area=None):
    try:
        j = json.loads('\n'.join(document))
        if service_area:
            prefixes = [p for sa in j for p in sa.get('ips', []) if sa.get('serviceArea') == service_area]
        else:
            prefixes = [p for sa in j for p in sa.get('ips', [])]
        return prefixes
    except Exception as e:
        raise e
    return []

def filter_ip_version(version, prefixes):
        if version == 4:
            prefixes = list(filter(lambda p: '.' in p, prefixes)) # dirty
        elif version == 6:
            prefixes = list(filter(lambda p: ':' in p, prefixes)) # dirty
        else:
            raise ValueError(f'Unknown ip version {version}')
        return prefixes

def get_blocklist(url):
    # scheme decection could be better but for now it will suffice
    online_schemes=['http', 'https']

    parser = None
    if isinstance(url, tuple):
        url, parser = url

    if any([url.startswith(f'{scheme}://') for scheme in online_schemes]):
        if parser:
            return parser(get_online_blocklist(url))
        else:
            return get_online_blocklist(url)

    if url.startswith('file://'):
        url = url[len('file://'):]
        with open(url, 'r') as f:
            return [line.strip() for line in f.readlines()]

    if url.startswith('asn://'):
        version, asn = url[len('asn://'):].split('/')
        try:
            if version == '6':
                p = subprocess.run(['bgpq4', '-6', '-F', '%n/%l\n', f"as{asn}"], capture_output=True)
            else:
                p = subprocess.run(['bgpq4', '-F', '%n/%l\n', f"as{asn}"], capture_output=True)
            lines = [line.strip() for line in p.stdout.decode().split('\n') if len(line) > 0]
            return lines
        except FileNotFoundError as e:
            print('bgpq4 not found: ASN based blocklists depend on the bgpq4 binary', file=sys.stderr)
            sys.exit(1)
        return []


@functools.lru_cache(100)
def get_online_blocklist(url):
    r = requests.get(url)
    if r.status_code == 200:
        return r.text.split("\n")
    return []

def fetch_blocklists(blocklists):
    return { url: get_blocklist(url) for url in blocklists}

def create_txt(provider, version, blocklists):
    name = f'{provider}-v{version}'
    output = []
    for url, bl in blocklists.items():
        output.append(f'# from {url}')
        bl = filter_ip_version(version, bl)
        output = output + bl
    with open(f'blocklists/{name}.txt', 'w') as f:
        f.writelines(line + '\n' for line in output)

def create_ipset(provider, version, blocklists):
    name = f'{provider}-v{version}'
    family = 'inet'
    if version == 6:
        family = 'inet6'
    output = []
    output.append(f'create {name} hash:net family {family} hashsize 1024 maxelem 65536')
    for url, bl in blocklists.items():
        output.append(f'# from {url}')
        bl = filter_ip_version(version, bl)
        output = output + [f'add {name} {entry}' for entry in bl]
    with open(f'blocklists/{name}.ipset', 'w') as f:
        f.writelines(line + '\n' for line in output)

with open("cloudburst.toml", "r") as f:
    config = toml.load(f)
    clouds = config.get('clouds', {})
    for provider, cloud_config in clouds.items():
       print(f"Generating blocklist for {provider}")
       blocklists = cloud_config.get('blocklists', [])
       parsers = cloud_config.get('parsers', [])
       blocklists = [(blocklist, globals().get(parser)) for blocklist, parser in zip_longest(blocklists, parsers)]
       blocklists = fetch_blocklists(blocklists)
       create_txt(provider, 4, blocklists)
       create_txt(provider, 6, blocklists)
       create_ipset(provider, 4,  blocklists)
       create_ipset(provider, 6,  blocklists)
