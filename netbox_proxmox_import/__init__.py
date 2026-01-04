from netbox.plugins import PluginConfig

import importlib.metadata

NAME = 'netbox_proxmox_import'

_DISTRIBUTION_METADATA = importlib.metadata.metadata(NAME)

DESCRIPTION = _DISTRIBUTION_METADATA['Summary']
VERSION = _DISTRIBUTION_METADATA['Version']

class NetBoxAccessListsConfig(PluginConfig):
    name = NAME
    verbose_name = 'NetBox Proxmox Import'
    description = DESCRIPTION
    version = VERSION
    base_url = 'nbp-sync'
    default_settings = {
        'debug': False,
    }

config = NetBoxAccessListsConfig
