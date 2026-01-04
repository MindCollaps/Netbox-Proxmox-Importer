from rest_framework import serializers

from netbox.api.serializers import NetBoxModelSerializer
from ..models import ProxmoxConnection

class ProxmoxConnectionSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_proxmox_import-api:proxmoxconnection-detail'
    )

    class Meta:
        model = ProxmoxConnection
        fields = (
            'id', 'url', 'cluster', 'domain', 'verify_ssl', 'user', 'port',
            'custom_fields', 'created', 'last_updated',
        )
