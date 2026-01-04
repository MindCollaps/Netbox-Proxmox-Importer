# Proxmox to NetBox Integration Plugin

> **Note:** This project is a copy of the unmaintained project at [https://gitlab.c3sl.ufpr.br/root/netbox-proxmox-import](https://gitlab.c3sl.ufpr.br/root/netbox-proxmox-import).

This is a NetBox plugin that fetches information from a Proxmox server and
imports it into NetBox. It simply imports the data over nicely.

## Features

* Imports virtual machines (and their interfaces) from Proxmox into NetBox.
* Supports synchronization of multiple clusters.
* Complete management through the UI.
* Automatically updates device and node information at regular intervals (maybe? I'll see about that).

## Compatibility

| NetBox Version | Plugin Version |
|---|---|
| 4.1.x | 1.0.0 |
| 4.2.x | 1.1.0 |
| 4.4.x | 1.1.3 |

## Installation

Regular plugin install.

1. Download and install the package:

   ```bash
   source /opt/netbox/venv/bin/activate
   pip install .
   ```

2. Enable the plugin in `configuration.py`:

   ```python
   PLUGINS = ['netbox_proxmox_import']
   ```

3. Run migrations and restart NetBox:

   ```bash
   cd /opt/netbox
   ./manage.py migrate
   sudo systemctl restart netbox
   ```

### NetBox Docker

If you are using NetBox Docker, you should create a custom Docker image.

1. Create a `Dockerfile` in the root of this repository:

   ```dockerfile
   FROM netboxcommunity/netbox:latest

   COPY . /source
   RUN /opt/netbox/venv/bin/pip install /source
   ```

2. Build and use this image instead of the standard `netboxcommunity/netbox`.

   ```bash
   docker build -t my-netbox-with-plugin .
   ```

#### Troubleshooting Connectivity (VPN/Firewall)

If your NetBox container cannot reach Proxmox (e.g., over a VPN), you might need to fix routing or NAT on the host.

**Symptoms:**
*   `Connection timed out` errors in logs.
*   `curl` from inside the container hangs.

**Fix (Masquerade Traffic):**
If your host is connected to a VPN (e.g., `tun0`) and NetBox is in a container (e.g., `br-custom`), the return traffic might be getting lost. You can force NAT for the container traffic:

1.  Find your NetBox container IP (e.g., `172.17.0.5`) and interface (e.g., `br-12345`).
2.  Add an iptables rule on the **HOST**:

    ```bash
    # Replace with your actual IPs and Interfaces
    sudo iptables -t nat -A POSTROUTING -s <NETBOX_CONTAINER_IP> -d <PROXMOX_IP> -o <VPN_INTERFACE> -j MASQUERADE
    ```

3.  Ensure forwarding is enabled:
    ```bash
    sudo iptables -I FORWARD -s <NETBOX_CONTAINER_IP> -d <PROXMOX_IP> -i <DOCKER_BRIDGE_IFACE> -o <VPN_INTERFACE> -j ACCEPT
    ```

#### Manual Installation in Docker

If you want to install manually inside a running container (for testing):

1.  Enter the container as root:
    ```bash
    docker exec -it -u root <container_name> bash
    ```

2.  Install using `uv` (since `pip` might be missing):
    ```bash
    source /opt/netbox/venv/bin/activate
    uv pip install .
    ```

### Debugging

To enable detailed debug logging (e.g., to see raw VM status data), add the following to your NetBox `configuration.py` (or `plugins.py`):

```python
PLUGINS_CONFIG = {
    'netbox_proxmox_import': {
        'debug': True,
    }
}
```

## Usage

Create your virtualization cluster as you would normally.

This plugin adds a model called ProxmoxCluster, which stores the actual
connection configuration to your Proxmox clusters. Access this page via the path `/plugins/nbp-sync/proxmox-connections` or using the sidebar, under "Plugins".

Each cluster connection gets its own configuration.

The current configuration options are:

* Domain (required): URL to access the Proxmox cluster (check your firewall and DNS!).
* User (required): Username to access the Proxmox API.
* Access Token (required): Token for this user to use the Proxmox API.
* Cluster (required): The actual cluster in NetBox this Proxmox connection will be associated to.

### Caution

Use a read-only Proxmox user! This plugin DOES NOT send writes to Proxmox!

After that you'll have a nice interface `/plugins/nbp-sync/proxmox-connections/<connection_id>`, from where you can manually synchronize the information.

It will also show what has changed and also inform you of any warnings or
errors.

### Note

The first sync generally takes the longest, as no information is present yet on
NetBox, so we create everything.
