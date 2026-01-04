import re
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

def is_debug():
    try:
        return settings.PLUGINS_CONFIG.get('netbox_proxmox_import', {}).get('debug', False)
    except Exception:
        return False


class NetBoxParser:


    def __init__(self, proxmox_connection):
        self.connection = proxmox_connection
        self.default_tag_color = "d1d1d1"


    def parse_tags(self, px_tags):
        nb_tags = []
        for name, color in px_tags.items():
            tag_slug = name.lower().replace(" ", "-").replace(".", "_")
            tag_slug = f"nbpsync__{tag_slug}"
            tag_color = self.default_tag_color if color is None else color
            nb_tags.append({
                "name": name,
                "slug": tag_slug,
                "color": tag_color,
                "object_types": ["virtualization.virtualmachine"],
            })
        return nb_tags

    def parse_vms(self, px_vm_list):
        nb_vms = []
        for vm in px_vm_list:
            nb_vms.append(self._parse_vm(vm))
        return nb_vms

    def _parse_vm(self, px_vm):
        status_raw = str(px_vm.get("status", "")).lower().strip()
        vm_status = "active" if status_raw == "running" else "offline"
        
        if is_debug():
            logger.info(f"Parsing VM {px_vm.get('name')} - Raw Status: '{status_raw}' -> NetBox Status: '{vm_status}'")
        
        # Calculate vcpus with defaults if missing
        sockets = int(px_vm.get("sockets", 1))
        cores = int(px_vm.get("cores", 1))
        vcpus = sockets * cores

        nb_vm = {
            "name": px_vm.get("name", f"VM-{px_vm.get('vmid')}"),
            "status": vm_status,
            # Note: will not set the node for the VM if the node itself
            # is not assigned to the virtualization cluster of the VM
            "device": {"name": px_vm.get("node")},
            "cluster": {"name": self.connection.cluster.name},
            "vcpus": vcpus,
            "memory": int(px_vm.get("memory", 0)),
            # "role": self.connection.vm_role_id or None,
            "disk": int(px_vm.get("maxdisk", 0) / 2 ** 20),  # B -> MB
            "tags": [{"name": tag} for tag in px_vm.get("tags", [])],
            "custom_fields": {"vmid": px_vm.get("vmid")},
        }
        return nb_vm

    def parse_vminterfaces(self, px_interface_list):
        nb_vminterfaces = []
        for px_interface in px_interface_list:
            mac, vlanid = self._extract_mac_vlan(px_interface["info"])
            interface = {
                "name": px_interface["name"],
                "virtual_machine": {"name": px_interface["vm"]},
                "mac_address": mac.upper(),
                "mode": "access",
                "untagged_vlan": {"vid": int(vlanid)},
            }
            nb_vminterfaces.append(interface)
        return nb_vminterfaces

    def _extract_mac_vlan(self, net_string):
        mac_match = re.search(r"([0-9A-Fa-f:]{17})", net_string)
        vlan_match = re.search(r"vmbr(\d+)", net_string)
        mac_address = mac_match.group(1) if mac_match else None
        vlan_id = vlan_match.group(1) if vlan_match else None
        return mac_address, vlan_id
