import json
from extras.models import Tag
from dcim.models import Device
from virtualization.models import VirtualMachine, VMInterface
from ipam.models import VLAN


class NetBoxCategorizer:
    def __init__(self, proxmox_connection):
        self.connection = proxmox_connection

        self.tag_warnings = set()
        self.vm_warnings = set()
        self.vminterface_warnings = set()

    def categorize_tags(self, parsed_tags):
        existing_tags_by_name = { tag.name: tag for tag in Tag.objects.all() }

        create = []
        update = []
        delete = []

        for px_tag in parsed_tags:
            if px_tag["name"] not in existing_tags_by_name:
                create.append(px_tag)
                continue
            nb_tag = existing_tags_by_name[px_tag["name"]]
            if not self._tags_equal(px_tag, nb_tag, existing_tags_by_name):
                update.append({"before": nb_tag, "after": px_tag})

        existing_tags_set = set(existing_tags_by_name.keys())
        parsed_tags_set = set(tag["name"] for tag in parsed_tags)
        deleted_tags_set = existing_tags_set - parsed_tags_set
        for tag_name in deleted_tags_set:
            delete.append(existing_tags_by_name[tag_name])

        return {
            "create": create,
            "update": update,
            "delete": delete,
            "warnings": list(self.tag_warnings),
        }

    def _tags_equal(self, px_tag, nb_tag, existing_tags_by_name={}):
        if px_tag["slug"] != nb_tag.slug:
            self.tag_warnings.add(
                f"Tag '{px_tag['name']}' already exists "
                f"and is not managed by this plugin!"
            )
            return True
        return px_tag["color"] == nb_tag.color

    def categorize_vms(self, parsed_vms):
        devices_by_name = {
            device.name: device for device in Device.objects.filter(cluster_id=self.connection.cluster.id)
        }
        existing_vms_by_name = {
            vm.name: vm for vm in VirtualMachine.objects.filter(cluster_id=self.connection.cluster.id)
        }
        # Create a lookup by VMID (custom field)
        existing_vms_by_vmid = {}
        for vm in existing_vms_by_name.values():
            vmid = vm.custom_field_data.get("vmid")
            if vmid:
                existing_vms_by_vmid[vmid] = vm

        tags_by_name = {
            t.name: t for t in Tag.objects.filter(slug__istartswith=f"nbpsync__")
        }

        create = []
        update = []
        delete = []

        names_to_create = set()
        names_to_update = set()
        
        # Track which existing VMs have been matched
        matched_existing_vms = set()

        for px_vm in parsed_vms:
            nb_vm = None
            
            # Try to match by VMID first (more reliable for renames)
            px_vmid = px_vm["custom_fields"].get("vmid")
            if px_vmid and px_vmid in existing_vms_by_vmid:
                nb_vm = existing_vms_by_vmid[px_vmid]
            
            # Fallback to name match if no VMID match
            if not nb_vm and px_vm["name"] in existing_vms_by_name:
                nb_vm = existing_vms_by_name[px_vm["name"]]

            if not nb_vm:
                if px_vm["name"] not in names_to_create:
                    names_to_create.add(px_vm["name"])
                    create.append(px_vm)
                    continue
            
            # Mark this existing VM as matched
            matched_existing_vms.add(nb_vm.id)

            if not self._vms_equal(px_vm, nb_vm, devices_by_name, tags_by_name):
                if px_vm["name"] not in names_to_update:
                    names_to_update.add(px_vm["name"])
                    update.append({"before": nb_vm, "after": px_vm})

        # Delete any existing VMs that were not matched
        for vm in existing_vms_by_name.values():
            if vm.id not in matched_existing_vms:
                delete.append(vm)

        return {
            "create": create,
            "update": update,
            "delete": delete,
            "warnings": list(self.vm_warnings),
        }

    def _vms_equal(self, px_vm, nb_vm, devices_by_name={}, tags_by_name={}):
        if px_vm["name"] != nb_vm.name:
            return False
        if devices_by_name.get(px_vm["device"]["name"]) is None:
            if Device.objects.filter(name=px_vm["device"]["name"]).exists():
                self.vm_warnings.add(
                    f"Device '{px_vm['device']['name']}' exists but is not assigned to Cluster "
                    f"'{self.connection.cluster.name}'."
                )
            else:
                self.vm_warnings.add(
                    f"Device '{px_vm['device']['name']}' not found. Please create it and assign to Cluster "
                    f"'{self.connection.cluster.name}'."
                )
        elif nb_vm.device is None:
            return False
        elif px_vm["device"]["name"] != nb_vm.device.name:
            return False
        if px_vm["status"] != nb_vm.status:
            return False
        if px_vm["vcpus"] != nb_vm.vcpus:
            return False
        if px_vm["memory"] != nb_vm.memory:
            return False
        if px_vm["disk"] != nb_vm.disk:
            return False
        if px_vm["custom_fields"]["vmid"] != nb_vm.custom_field_data["vmid"]:
            return False
        nb_tags = set([tag.name for tag in nb_vm.tags.all()])
        for px_tag in px_vm["tags"]:
            if px_tag["name"] not in nb_tags and tags_by_name.get(px_tag["name"]) is not None:
                return False
        return True

    def categorize_vminterfaces(self, parsed_vminterfaces):
        existing_vms = VirtualMachine.objects.filter(cluster_id=self.connection.cluster.id)
        existing_vminterfaces_by_name = {
            vmi.name: vmi for vmi in \
            VMInterface.objects.filter(virtual_machine__in=existing_vms)
        }
        vlans_by_vid = {vlan.vid: vlan for vlan in VLAN.objects.all()}

        create = []
        update = []
        delete = []

        names_to_create = set()
        names_to_update = set()

        for px_vmi in parsed_vminterfaces:
            if px_vmi["name"] not in existing_vminterfaces_by_name:
                if px_vmi["name"] not in names_to_create:
                    # Not sure why yet, but randomly proxmox sends me duplicated stuff
                    # (maybe in between migrations it gets messed up?)
                    names_to_create.add(px_vmi["name"])
                    create.append(px_vmi)
                    continue
            nb_vmi = existing_vminterfaces_by_name[px_vmi["name"]]
            if not self._vminterfaces_equal(px_vmi, nb_vmi, vlans_by_vid):
                if px_vmi["name"] not in names_to_update:
                    names_to_update.add(px_vmi["name"])
                    update.append({"before": nb_vmi, "after": px_vmi})

        existing_vminterfaces_set = set(existing_vminterfaces_by_name.keys())
        parsed_vminterfaces_set = set(vmi["name"] for vmi in parsed_vminterfaces)
        deleted_vminterfaces_set = existing_vminterfaces_set - parsed_vminterfaces_set

        for vmi_name in deleted_vminterfaces_set:
            delete.append(existing_vminterfaces_by_name[vmi_name])

        return {
            "create": create,
            "update": update,
            "delete": delete,
            "warnings": list(self.vminterface_warnings),
        }

    def _vminterfaces_equal(self, px_vmi, nb_vmi, vlans_by_vid={}):
        # Check VLAN
        px_vid = px_vmi.get("untagged_vlan", {}).get("vid") if px_vmi.get("untagged_vlan") else None
        
        if px_vid is not None:
            if vlans_by_vid.get(px_vid) is None:
                self.vminterface_warnings.add(
                    f"VLAN with VID={px_vid} was not found!"
                )
                # If VLAN doesn't exist in NetBox, we can't assign it.
                # But we should still check if other fields match.
                # If NetBox has a VLAN assigned but Proxmox wants a non-existent one, 
                # we technically differ, but we can't fix it.
            elif nb_vmi.untagged_vlan is None:
                return False
            elif int(px_vid) != int(nb_vmi.untagged_vlan.vid):
                return False
        else:
            # Proxmox has no VLAN (untagged)
            if nb_vmi.untagged_vlan is not None:
                return False

        if px_vmi["name"] != nb_vmi.name:
            return False
        if px_vmi["virtual_machine"]["name"] != nb_vmi.virtual_machine.name:
            return False
        
        px_mac = str(px_vmi["mac_address"]).upper()
        nb_macs = [str(m.mac_address).upper() for m in nb_vmi.mac_addresses.all()]
        
        if not nb_macs:
             if px_mac: return False
        else:
             if px_mac not in nb_macs:
                 return False
        
        # Check IPs
        px_ips = set(px_vmi.get("ip_addresses", []))
        # Use the reverse relation from IPAddress to VMInterface
        nb_ips = set([str(ip.address) for ip in nb_vmi.ip_addresses.all()])
        
        if px_ips != nb_ips:
            return False

        return True
