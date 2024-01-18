# Cloudburst

Cloudburst is a tool to simulate what happens if a large party such as a cloud, CDN or other large service provider disappears from the Internet.
It can therefore be used to:

- Identify dependencies on single large cloud providers.
- Be used for crisis exercises and scenarios.
- Create awareness on Internet centralization.

Read more about Cloudburst in [our blog post](https://www.sidnlabs.nl/en/news-and-blogs/simulating-cloud-provider-downtime-with-cloudburst).

## Running Cloudburst

Cloudburst consists of several components, most require privileged access to the system.
We therefore recommend to run Cloudburst in its own virtual machine or on a VPS.

The Cloudburst external user interface allows users to set up a VPN connection to the VPS and allows them to connect to the Internet via the VPS.
When connected via the VPN, a user can access the Cloudburst internal user interface and configure which cloud providers to disable.

### 1. Install necessary components

We tested Cloudburst on Debian 12, but it should work (maybe with minor modifications) on other versions of Debian and Ubuntu.

*These instructions assume that Cloudburst runs on its own machine and may overwrite otherwise critical files*

Install dependency packages:
```
# apt-get install git vim-tiny tmux docker.io docker-compose python3-pip python3-requests python3-bottle python3-toml unbound nginx acmetool wireguard-tools bgpq4 ipset apache2-utils
# systemctl stop nginx.service
# systemctl stop unbound.service
```
Clone this repository on the machine:
```
# cd /root
# git clone https://github.com/SIDN/cloudburst
```
Update and load blocklists, and setup wireguard-ui for the creation of WireGuard tunnels:
```
# cd /root/cloudburst && python3 update_blocklists.py
# cd /root/cloudburst && sh load_blocklists.sh
# cd /root/cloudburst/wg-ui && sh build.sh   # you probably want this in a tmux
```

### 2. Configure nginx

Note that if you start nginx at this point it will fail since nginx explicitly binds to a local interface configured by wg-ui.

```
# cd /root/cloudburst
# cp examples/nginx-cloudburst.conf.example /etc/nginx/sites-enabled/cloudburst
# rm /etc/nginx/sites-enabled/default        # disable default virtual host
# htpasswd -c /etc/nginx/htpasswd demo       # provide a password to prevent the Internet from creating VPN tunnels.
```

### 3. Configure unbound

```
# cd /root/cloudburst
# cp examples/unbound-cloudburst.conf.example /etc/unbound/unbound.conf
```

### 4. Change configuration to match your local situation

* Register a memorable DNS name for the Cloudburst service and use some service to obtain TLS certificates.
* Replace instances of `cloudburst.example.nl` in _/etc/unbound/unbound.conf_ to your specified DNS name.
* Change `WIREGUARD_UI_WG_ENDPOINT` in _wg-ui/docker-compose.yml_ to match the public IP of the host; this is where VPN clients can connect to.
* Change `ssl_certificate` and `ssl_certificate_key` in _/etc/nginx/sites-enabled/cloudburst_ to match the paths to your TLS certificate and TLS key.
* In _/etc/nginx/sites-enabled/cloudburst_ you can whitelist IP ranges to VPNs without requiring a user:password combination.

### 4. Run the Cloudburst user interface and the wg-ui API

We run Cloudburst in a tmux session for easy troubleshooting:

```
# cd /root/cloudburst
# tmux new-session \; \
    rename-window wireguard-ui \; \
    send-keys 'cd /root/cloudburst/wg-ui && bash start.sh' C-m \; \
    new-window \; \
    rename-window cb-ui \; \
    send-keys 'python3 cloudburst.py' C-m \; \
    new-window \; \
    rename-window shell \; \
    send-keys 'sleep 3' C-m \; \
    send-keys 'systemctl restart unbound' C-m \; \
    send-keys 'systemctl restart nginx' C-m \; \
    select-window -t -0 ;
```

### 5. Use Cloudburst on your devices

Now that Cloudburst is up and running, you can connect devices to Cloudburst.
Generally, you open a web browser and point it to the DNS name that you chose earlier and follow the instructions to configure that device to use Cloudburst.

For your convenience, we described the typical workflow for different types of devices in a bit more detail (substitute *cloudburst.example.nl* with the DNS name you use):
- For PCs: open a web browser on your PC and navigate to cloudburst.example.nl. Create a WireGuard tunnel there. Download the WireGuard configuration and configure WireGuard on your PC. Then use the web browser to go to cloudburst.example.nl again to configure which cloud providers to disable.
- For mobile devices: open a web browser on your PC and navigate to cloudburst.example.nl. Create a WireGuard tunnel there. Then take your mobile device and scan the QR code on the PC screen to add the WireGuard tunnel to your mobile device and activate the tunnel. Then, open cloudburst.example.nl on your mobile device to configure which cloud providers to disable.

## Updating blocklists

Whenever you need to update the blocklists run `reload_blocklists.py`
This script refreshes the blocklists in the _blocklists_ folder.

```
# cd /root/cloudburst
# python3 reload_blocklists.py
```
