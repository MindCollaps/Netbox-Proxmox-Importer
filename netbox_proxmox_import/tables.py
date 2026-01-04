import django_tables2 as tables

from netbox.tables import NetBoxTable, ChoiceFieldColumn
from .models import ProxmoxConnection


class ProxmoxConnectionTable(NetBoxTable):

    domain = tables.Column(linkify=True)
    # id = tables.Column(linkify=True)
    cluster = tables.Column(linkify=True)

    class Meta(NetBoxTable.Meta):
        model = ProxmoxConnection
        fields = ('pk', 'id', 'cluster', 'domain', 'user')
        default_columns = ('domain', 'user')
