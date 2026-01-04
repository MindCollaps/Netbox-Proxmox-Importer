# Proxmox to NetBox Integration Plugin

> **Note:** This project is a copy of the unmaintained project at [https://gitlab.c3sl.ufpr.br/root/netbox-proxmox-import](https://gitlab.c3sl.ufpr.br/root/netbox-proxmox-import).

This is a NetBox plugin that fetches information from a Proxmox server and
imports it into NetBox. It simply imports the data over nicely.

## Features

* Imports virtual machines (and their interfaces) from Proxmox into NetBox.
* Supports synchronization of multiple clusters.
* Complete management through the UI.
* Automatically updates device and node information at regular intervals (maybe? I'll see about that).
* **IP Address Sync**: Syncs IP addresses from VMs to NetBox interfaces (requires QEMU Guest Agent).

## Prerequisites

### QEMU Guest Agent (for IP Sync)

To synchronize IP addresses, the **QEMU Guest Agent** must be installed and running on your VMs, and enabled in Proxmox.

1.  **Enable in Proxmox**: Go to VM > Options > QEMU Guest Agent > Enable.
2.  **Install on Guest**:
    *   **Linux (Debian/Ubuntu)**: `sudo apt install qemu-guest-agent && sudo systemctl enable --now qemu-guest-agent`
    *   **Linux (RHEL/CentOS)**: `sudo yum install qemu-guest-agent && sudo systemctl enable --now qemu-guest-agent`
    *   **Linux (Arch)**: `sudo pacman -S qemu-guest-agent && sudo systemctl enable --now qemu-guest-agent`
    *   **OPNsense**: Install `os-qemu-guest-agent` via **System > Firmware > Plugins** (enable community plugins).
    *   **Home Assistant OS**: Built-in. Just enable "QEMU Guest Agent" in Proxmox VM Options.
    *   **Windows**: Install the [VirtIO Drivers](https://pve.proxmox.com/wiki/Windows_VirtIO_Drivers).

## Compatibility

| NetBox Version | Plugin Version |
|---|---|
| 4.1.x | 1.0.0 |
| 4.2.x | 1.1.0 |
| 4.4.x | 1.1.3 |

## Installation

### Standard Installation (from Source/Zip)

1. Download the source code or the release zip file (e.g., `netbox-proxmox-importer-v1.1.3.zip`) to your NetBox server.

2. Activate the NetBox virtual environment and install the package:

   ```bash
   source /opt/netbox/venv/bin/activate
   # If installing from a directory:
   pip install .
   # If installing from a zip file:
   pip install /path/to/netbox-proxmox-importer-v1.1.5.zip
   ```

3. Enable the plugin in `configuration.py`:

   ```python
   PLUGINS = ['netbox_proxmox_import']
   ```

4. Run migrations and restart NetBox:

   ```bash
   cd /opt/netbox
   ./manage.py migrate
   sudo systemctl restart netbox
   ```

### Permissions

The Proxmox user/token used by this plugin requires the following permissions:

*   `PVEAuditor` (role): Read-only access to cluster configuration and VM settings.
*   `VM.Monitor` (permission): Required to query the QEMU Guest Agent for IP addresses.

If you are creating a custom role, ensure it has:
*   `VM.Audit`
*   `VM.Config.Options` (read)
*   `VM.Monitor`
*   `Sys.Audit`

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

### Configuration

Add the plugin configuration to your `configuration.py` (or `plugins.py`):

```python
PLUGINS_CONFIG = {
    'netbox_proxmox_import': {
        'debug': True, # Enable detailed debug logging
        'sync_interval': 300, # Sync every 300 seconds (5 minutes). Set to 0 to disable automatic sync.
    }
}
```

### Periodic Sync

You can enable automatic periodic synchronization by setting `sync_interval` in the plugin configuration (see above). This uses the NetBox background worker (RQ).

Alternatively, you can run the synchronization manually or via cron using the management command:

```bash
python manage.py proxmox_sync
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
