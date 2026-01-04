from netbox.forms import NetBoxModelForm
from .models import ProxmoxConnection


class ProxmoxConnectionForm(NetBoxModelForm):

    class Meta:
        model = ProxmoxConnection
        fields = ('domain', 'port', 'verify_ssl', 'user', 'token_id', 'token_secret', 'cluster')
