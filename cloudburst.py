import json
import os
import subprocess
import time
import toml

from bottle import request, response, route, run, template
from bottle import static_file, TEMPLATE_PATH, abort
from ipaddress import ip_address, ip_network

try:
    with open("cloudburst.toml", "r") as f:
        config = toml.load(f)
        ui_config = config.get('cb-ui', {})
        clouds = config.get('clouds', {})

        # update globals
        IPTABLES = ui_config.get('iptables','/sbin/iptables')
        IP6TABLES = ui_config.get('ip6tables','/sbin/ip6tables')
        LISTEN = ui_config.get('listen', '127.0.0.1')
        LOOPBACK_IP_ADDRS = ui_config.get('loopback_addrs', [LISTEN])
        INTERNAL_NETS = ui_config.get('internal_networks', ["127.0.0.1", "::1"])
        BURSTABLE_CLOUDS = {c['ipset']: {'name': c['name']} for c in clouds.values()}
        CLOUDS_FILTER = ui_config.get('shortlist', [])
except Exception as e:
    raise e

TEMPLATE_PATH.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "static/internal")))


class Blocklist(object):
    def __init__(self, ip):
        parsed_ip = ip_address(ip)
        self.ip = ip
        self.version = parsed_ip.version
        self.chain_name = self.chain_name(ip)
        self._exists = False

    @staticmethod
    def chain_name(ip):
        '''constructs a chain from an ip'''
        if ':' in ip:
            # Some IPv6 addresses are too long (must be **under 29 chars**)
            # We need to split on after /64
            # otoh is better to remove the : and truncate such that we have the last 28 chars
            ip = ip_address(ip).compressed # compress if possible
            ip = ip.replace(':', '') # drop colons
            if len(ip) == 0:
                return 0
            elif len(ip) > 28:
                return ip[-28:]
            else:
                return ip
        return ip

    @staticmethod
    def run_iptables(cmd, version, silence=False):
        if version == 4:
            cmd = [IPTABLES, *cmd ]
        elif version == 6:
            cmd = [IP6TABLES, *cmd ]
        else:
            raise ValueError(f'Unknown ip version: {version}')

        try:
            result = subprocess.run(cmd, check=True, capture_output=True)
            ret = False, result.stdout
        except subprocess.CalledProcessError as e:
            ret = True, e
        except Exception as e:
            raise e
        error, message = ret
        if error and not silence:
            print(f"running {' '.join(cmd)} failed: {message}")
        return ret

    def _create(self):
        """ Create a chain and the forwarding rule """
        ip = self.ip
        chain = self.chain_name
        cmd = f'-N {chain}'.split()
        self.run_iptables(cmd, self.version)
        cmd = f'-A FORWARD -s {ip} -j {chain}'.split()
        self.run_iptables(cmd, self.version)

    def destroy(self):
        """ Destroys the chain and the forwarding rule """
        self.clear() # chain needs to be empty before removal
        time.sleep(.1) # clearing takes time and has to be done for removal
        chain = self.chain_name
        cmd = f'-D FORWARD -s {self.ip} -j {chain}'.split()
        self.run_iptables(cmd, self.version)
        cmd = f'-X {chain}'.split()
        self.run_iptables(cmd, self.version)

    def clear(self):
        """ Removes rules from the chain """
        chain = self.chain_name
        cmd = ['-F', chain]
        self.run_iptables(cmd, self.version)

    def system_exists(self):
        """ Checks whether the chain exists on the system """
        chain = self.chain_name
        cmd = f'-L {chain}'.split()
        error, message = self.run_iptables(cmd, self.version, silence=True)
        return not error

    def exists(self):
        """ Checks whether the chain exists """
        if not self._exists:
            self._exists = self.system_exists()
        return self._exists

    def block_cloud(self, cloud):
        chain = self.chain_name
        version = self.version
        print(f'bursting {cloud} for {self.ip}')
        cmd = ['-A', chain, '-m','set','--match-set', f'{cloud}-v{version}','dst','-j','REJECT']
        self.run_iptables(cmd, version)

    def __enter__(self):
        if not self.exists():
            self._create()
        return self

    def __exit__(self, type, value, traceback):
        pass

def get_clouds(shortlist=True):
    """ Returns lists of clouds """
    clouds = BURSTABLE_CLOUDS
    if shortlist:
        clouds = {k: v for k, v in BURSTABLE_CLOUDS.items() if k in CLOUDS_FILTER}
    return clouds

def get_ip():
    """ Try to get the IP from http headers """
    headers_by_priority = ['HTTP_X_REAL_IP', 'HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR']
    for header in headers_by_priority:
        ip = request.environ.get(header)
        if ip:
            return ip
    return None

def burst(clouds):
    ip = get_ip()
    with Blocklist(ip) as blocklist:
        blocklist.clear()
        #blocklist.destroy()
    friendly_names = []
    for cloud in clouds:
        valid_cloud = BURSTABLE_CLOUDS.get(cloud)
        if valid_cloud:
            with Blocklist(ip) as blocklist:
                blocklist.block_cloud(cloud)
            friendly_names.append(valid_cloud['name'])
    return template('blocked.html', clouds=', '.join(friendly_names))

def is_internal(ip):
    if ip is None:
        return False
    address = ip_address(ip)
    internal = any([address in ip_network(net) for net in INTERNAL_NETS])
    return internal

@route('/')
def index(filename='index.html'):
    ip = get_ip()
    if is_internal(ip):
        return static_file(filename, root='static/internal')
    else:
        resp = static_file(filename, root='static/external')
        wguser = request.get_cookie("wguser")
        if not wguser or wguser == "anonymous":
            wguser = request.environ.get('HTTP_X_REQUEST_ID')
        if (wguser):
            resp.set_cookie("wguser", wguser)
        else:
            resp.set_cookie("wguser", "anonymous")
    return resp

@route('/faq')
def faq():
    return static_file('faq.html', root='static/external')

@route('/full')
def full():
    ip = get_ip()
    if is_internal(ip):
        return static_file('full.html', root='static/internal')
    abort(404, 'Not found.')

@route('/static/<filename>')
def static(filename):
    """ Serve static files """
    return static_file(filename, root='static/other/')

@route('/burst',  method="ANY")
def burst_post():
    clouds = []
    for c in BURSTABLE_CLOUDS.keys():
        if request.forms.get(c) == 'on':
            clouds.append(c)
    response.set_cookie("blocked", '-'.join(clouds))
    return burst(clouds)

@route('/clouds')
def get_supported_clouds():
    """ Obtains shortlist of supported cloudproviders """
    return json.dumps(get_clouds())

@route('/allclouds')
def get_all_clouds():
    """ Obtains list of supported cloudproviders """
    return json.dumps(get_clouds(shortlist=False))

run(host=LISTEN, port=8080)
