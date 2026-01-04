from proxmoxer import ProxmoxAPI
import logging
import re
from django.conf import settings

logger = logging.getLogger(__name__)

def is_debug():
    try:
        return settings.PLUGINS_CONFIG.get('netbox_proxmox_import', {}).get('debug', False)
    except Exception:
        return False


class Proxmox:


    def __init__(self, config):
        try:
            self.proxmox = ProxmoxAPI(
                config["host"],
                port=config["port"],
                user=config["user"],
                token_name=config["token"]["name"],
                token_value=config["token"]["value"],
                verify_ssl=config["verify_ssl"],
                timeout=30  # Increased timeout to 30 seconds
            )
        except Exception as e:
            logger.exception(f"Failed to initialize Proxmox connection to {config.get('host')}")
            raise e
        self.vminterfaces = []

    def get_tags(self):
        try:
            options = self.proxmox.cluster.options.get()
            tags = {}
            
            # Handle allowed-tags if present
            allowed_tags = options.get("allowed-tags")
            if allowed_tags:
                # Ensure it's iterable
                if isinstance(allowed_tags, str):
                     # If it's a comma separated string
                     allowed_tags = allowed_tags.split(',')
                
                for tag in allowed_tags:
                    tags[tag.strip()] = None
            
            # Handle tag-style if present
            tag_style = options.get("tag-style")
            if tag_style and isinstance(tag_style, dict):
                color_map = tag_style.get("color-map")
                if color_map:
                    for tag in color_map.split(';'):
                        if ':' in tag:
                            parts = tag.split(':')
                            name = parts[0]
                            color = parts[1]
                            tags[name] = color
            
            return tags
        except Exception as e:
            logger.warning(f"Failed to retrieve tags from Proxmox: {e}")
            return {}

    def get_cluster(self):
        try:
            return self.proxmox.cluster.status.get()[0]
        except Exception as e:
            logger.exception("Failed to retrieve cluster status from Proxmox")
            raise e

    def get_vms(self):
        try:
            vm_resources = self.proxmox.cluster.resources.get(type="vm")
            vms = []
            for vm in vm_resources:
                try:
                    vm_config = self.proxmox.nodes(vm['node']).qemu(vm['vmid']).config.get()
                    # Fetch authoritative status
                    current_state = self.proxmox.nodes(vm['node']).qemu(vm['vmid']).status.current.get()
                except Exception as e:
                    logger.warning(f"Failed to retrieve config/status for VM {vm.get('vmid')} on node {vm.get('node')}: {e}")
                    continue

                # Ensure name exists
                if "name" not in vm_config:
                    vm_config["name"] = vm.get("name", str(vm.get("vmid")))

                # Try to get agent network info
                agent_interfaces = []
                try:
                    # Only try if VM is running
                    if current_state.get("status") == "running":
                        agent_info = self.proxmox.nodes(vm['node']).qemu(vm['vmid']).agent('network-get-interfaces').get()
                        if agent_info and 'result' in agent_info:
                            agent_interfaces = agent_info['result']
                            if is_debug():
                                logger.info(f"VM {vm_config.get('name')} - Agent Interfaces: {len(agent_interfaces)} found")
                except Exception as e:
                    # Agent might not be running or installed, or QEMU agent not enabled
                    if is_debug():
                        logger.info(f"VM {vm_config.get('name')} - Agent check failed: {e}")
                    pass

                self._add_vminterfaces(vm_config, agent_interfaces)
                
                # Use status from current_state if available, else fallback to resource list
                status = current_state.get("status", vm.get("status", "unknown"))
                
                vm_config["tags"] = [] if vm.get("tags") is None else str(vm.get("tags", "")).split(';')
                vm_config["maxdisk"] = int(vm.get("maxdisk", 0))
                vm_config["maxcpu"] = int(vm.get("maxcpu", 0))
                vm_config["vmid"] = vm.get("vmid")
                vm_config["node"] = vm.get("node")
                vm_config["status"] = status
                
                if is_debug():
                    logger.info(f"VM {vm_config.get('name')} ({vm.get('vmid')}) - Raw Status: {status}")
                
                vms.append(vm_config)
            return vms
        except Exception as e:
            logger.exception("Failed to retrieve VMs from Proxmox")
            raise e

    def _add_vminterfaces(self, vm_config, agent_interfaces=[]):
        for key in vm_config:
            if key.startswith('net'):
                # Extract MAC from config string (e.g., virtio=AA:BB:CC:DD:EE:FF,...)
                mac_match = re.search(r"([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})", vm_config[key])
                mac_address = mac_match.group(0).upper() if mac_match else None
                
                ips = []
                if mac_address and agent_interfaces:
                    for iface in agent_interfaces:
                        if iface.get('hardware-address', '').upper() == mac_address:
                            for ip_info in iface.get('ip-addresses', []):
                                ip_addr = ip_info.get('ip-address')
                                if ip_addr and not ip_addr.startswith('fe80::') and not ip_addr.startswith('127.'):
                                    # Include CIDR if available, otherwise just IP
                                    prefix = ip_info.get('prefix')
                                    if prefix:
                                        ips.append(f"{ip_addr}/{prefix}")
                                    else:
                                        ips.append(ip_addr)
                
                if is_debug() and ips:
                    logger.info(f"VM {vm_config.get('name')} - Interface {key} - IPs found: {ips}")

                self.vminterfaces.append({
                    "vm": vm_config["name"],
                    "name": f"{vm_config['name']}:{key}",
                    "info": vm_config[key],
                    "ips": ips
                })

    def get_vminterfaces(self):
        if len(self.vminterfaces) == 0:
            self.get_vms()
        return self.vminterfaces
