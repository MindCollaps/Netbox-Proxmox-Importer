import json
from django.core.exceptions import ObjectDoesNotExist
from django.core.serializers import serialize
from django.contrib.contenttypes.models import ContentType
from extras.models import Tag
from dcim.models import Device, MACAddress
from virtualization.models import VirtualMachine, VMInterface
from ipam.models import VLAN, IPAddress


class NetBoxUpdater:
    def __init__(self, proxmox_connection):
        self.connection = proxmox_connection

    def update_tags(self, categorized_tags, nodelete_tagnames=set()):
        errors = []
        created = []
        updated = []
        deleted = []

        vm_contenttype = ContentType.objects.get(app_label="virtualization", model="virtualmachine")

        for tag in categorized_tags["create"]:
            try:
                new_tag = Tag.objects.create(
                    name=tag["name"],
                    slug=tag["slug"],
                    color=tag["color"],
                    # object_types=[vm_contenttype]
                )
                new_tag.object_types.set([vm_contenttype.id])
                created.append(new_tag)
            except Exception as e:
                errors.append(e)
        # ======================================================================================== #
        for tag in categorized_tags["update"]:
            updated_tag = tag["before"]
            updated_tag.slug = tag["after"]["slug"]
            updated_tag.color = tag["after"]["color"]
            try:
                # Note: if another cluster has a different color this will keep updating too
                # Yeah... Idk man... Multi-cluster while managing tags too is weird
                updated_tag.save()
                updated_tag.object_types.set([vm_contenttype.id])
                updated.append(updated_tag)
            except Exception as e:
                errors.append(e)
        # ======================================================================================== #
        for tag in categorized_tags["delete"]:
            try:
                if tag.name not in nodelete_tagnames:
                    # Store ID and string representation before deletion
                    tag_id = tag.pk
                    tag_str = str(tag)
                    
                    tag.delete()
                    
                    # Append dict instead of object
                    deleted.append({"pk": tag_id, "model": "extras.tag", "fields": {"name": tag_str}})
            except Exception as e:
                errors.append(e)

        return {
            "created": json.loads(serialize("json", created)),
            "updated": json.loads(serialize("json", updated)),
            "deleted": deleted, # Return list of dicts
            "errors": [str(e) for e in errors],
            "warnings": categorized_tags["warnings"]
        }

    def update_vms(self, categorized_vms):
        errors = []
        created = []
        updated = []
        deleted = []

        tags_by_name = {
            t.name: t for t in Tag.objects.filter(slug__istartswith=f"nbpsync__")
        }
        devices_by_name = {
            device.name: device for device in Device.objects.filter(cluster=self.connection.cluster)
        }

        for vm in categorized_vms["create"]:
            try:
                new_vm = VirtualMachine.objects.create(
                    name=vm["name"],
                    status=vm["status"],
                    device=devices_by_name.get(vm["device"]["name"]),
                    cluster=self.connection.cluster,
                    vcpus=vm["vcpus"],
                    memory=vm["memory"],
                    disk=vm["disk"],
                    # tags=[tags_by_name.get(tag["name"]) for tag in vm["tags"]],
                    custom_field_data=vm["custom_fields"],
                )
                tags = [ tags_by_name.get(tag["name"]) for tag in vm["tags"] ]
                new_vm.save()
                new_vm.tags.set([ tag for tag in tags if tag is not None ])
                created.append(new_vm)
            except Exception as e:
                errors.append(e)
        # ======================================================================================== #
        for vm in categorized_vms["update"]:
            updated_vm = vm["before"]
            updated_vm.name = vm["after"]["name"]  # Update name if changed
            updated_vm.status = vm["after"]["status"]
            updated_vm.vcpus = vm["after"]["vcpus"]
            updated_vm.memory = vm["after"]["memory"]
            updated_vm.disk = vm["after"]["disk"]
            updated_vm.custom_field_data["vmid"] = vm["after"]["custom_fields"]["vmid"]
            updated_vm.device = devices_by_name.get(vm["after"]["device"]["name"])
            try:
                tags = [ tags_by_name.get(tag["name"]) for tag in vm["after"]["tags"] ]
                updated_vm.save()
                updated_vm.tags.set([ tag for tag in tags if tag is not None ])
                updated.append(updated_vm)
            except Exception as e:
                errors.append(e)
        # ======================================================================================== #
        for vm in categorized_vms["delete"]:
            try:
                # Store ID and string representation before deletion
                vm_id = vm.pk
                vm_str = str(vm)
                
                vm.delete()
                
                # Append dict instead of object
                deleted.append({"pk": vm_id, "model": "virtualization.virtualmachine", "fields": {"name": vm_str}})
            except Exception as e:
                errors.append(e)

        return {
            "created": json.loads(serialize("json", created)),
            "updated": json.loads(serialize("json", updated)),
            "deleted": deleted, # Return list of dicts
            "errors": [str(e) for e in errors],
            "warnings": categorized_vms["warnings"]
        }
    def update_vminterfaces(self, categorized_vminterfaces):
        errors = []
        created = []
        updated = []
        deleted = []

        vms_by_name = {
            vm.name: vm for vm in VirtualMachine.objects.filter(cluster=self.connection.cluster)
        }
        vlans_by_vid = { vlan.vid: vlan for vlan in VLAN.objects.all() }
        vminterface_ct = ContentType.objects.get_for_model(VMInterface)

        for vmi in categorized_vminterfaces["create"]:
            try:
                new_vmi = VMInterface.objects.create(
                    name=vmi["name"],
                    virtual_machine=vms_by_name.get(vmi["virtual_machine"]["name"]),
                    mode=vmi["mode"],
                    untagged_vlan=vlans_by_vid.get(vmi["untagged_vlan"]["vid"]) if vmi["untagged_vlan"] else None,
                )
                
                if vmi["mac_address"]:
                    MACAddress.objects.update_or_create(
                        mac_address=vmi["mac_address"],
                        defaults={
                            'assigned_object_type': vminterface_ct,
                            'assigned_object_id': new_vmi.pk
                        }
                    )
                
                self._update_ips(new_vmi, vmi.get("ip_addresses", []))
                
                created.append(new_vmi)
            except Exception as e:
                errors.append(e)
        # ======================================================================================== #
        for vmi in categorized_vminterfaces["update"]:
            updated_vmi = vmi["before"]
            updated_vmi.mode = vmi["after"]["mode"]
            updated_vmi.untagged_vlan = vlans_by_vid.get(vmi["after"]["untagged_vlan"]["vid"]) if vmi["after"]["untagged_vlan"] else None
            updated_vmi.virtual_machine = vms_by_name.get(vmi["after"]["virtual_machine"]["name"])
            try:
                updated_vmi.save()
                
                if vmi["after"]["mac_address"]:
                    mac_obj, _ = MACAddress.objects.update_or_create(
                        mac_address=vmi["after"]["mac_address"],
                        defaults={
                            'assigned_object_type': vminterface_ct,
                            'assigned_object_id': updated_vmi.pk
                        }
                    )
                    # Delete other MACs assigned to this interface
                    MACAddress.objects.filter(
                        assigned_object_type=vminterface_ct,
                        assigned_object_id=updated_vmi.pk
                    ).exclude(pk=mac_obj.pk).delete()
                else:
                    MACAddress.objects.filter(
                        assigned_object_type=vminterface_ct,
                        assigned_object_id=updated_vmi.pk
                    ).delete()

                self._update_ips(updated_vmi, vmi["after"].get("ip_addresses", []))

                updated.append(updated_vmi)
            except Exception as e:
                errors.append(e)
        # ======================================================================================== #
        for vmi in categorized_vminterfaces["delete"]:
            try:
                # Store ID and string representation before deletion for serialization
                vmi_id = vmi.pk
                vmi_str = str(vmi)
                
                MACAddress.objects.filter(
                    assigned_object_type=vminterface_ct,
                    assigned_object_id=vmi.pk
                ).delete()
                vmi.delete()
                
                # Create a dummy object or dict for the response since the real object is gone
                # and Django serializer can't handle deleted objects with M2M relations
                deleted.append({"pk": vmi_id, "model": "virtualization.vminterface", "fields": {"name": vmi_str}})
            except ObjectDoesNotExist:
                # in case it was cascade-deleted by a VM deletion
                deleted.append({"pk": vmi.pk if vmi.pk else 0, "model": "virtualization.vminterface", "fields": {"name": str(vmi)}})
            except Exception as e:
                errors.append(e)

        return {
            "created": json.loads(serialize("json", created)),
            "updated": json.loads(serialize("json", updated)),
            "deleted": deleted, # Now returning a list of dicts, not a serialized string
            "errors": [str(e) for e in errors],
            "warnings": categorized_vminterfaces["warnings"],
        }

    def _update_ips(self, vmi_obj, ip_list):
        vminterface_ct = ContentType.objects.get_for_model(VMInterface)
        
        if not ip_list:
            # If no IPs provided, unassign all currently assigned IPs
            IPAddress.objects.filter(
                assigned_object_type=vminterface_ct,
                assigned_object_id=vmi_obj.pk
            ).update(assigned_object_id=None, assigned_object_type=None)
            return

        current_ips = {str(ip.address): ip for ip in IPAddress.objects.filter(
            assigned_object_type=vminterface_ct,
            assigned_object_id=vmi_obj.pk
        )}
        target_ips = set(ip_list)
        
        # Assign/Create new IPs
        for ip_str in target_ips:
            if ip_str not in current_ips:
                try:
                    # Check if IP exists anywhere
                    ip_obj = IPAddress.objects.filter(address=ip_str).first()
                    if not ip_obj:
                        ip_obj = IPAddress.objects.create(
                            address=ip_str,
                            status='active'
                        )
                    
                    # Assign to this interface
                    ip_obj.assigned_object_type = vminterface_ct
                    ip_obj.assigned_object_id = vmi_obj.pk
                    ip_obj.save()
                except Exception as e:
                    # Log error?
                    pass

        # Unassign removed IPs
        for ip_str, ip_obj in current_ips.items():
            if ip_str not in target_ips:
                ip_obj.assigned_object_type = None
                ip_obj.assigned_object_id = None
                ip_obj.save()


    def create_mac_address(self, mac_address):
        return new_mac
