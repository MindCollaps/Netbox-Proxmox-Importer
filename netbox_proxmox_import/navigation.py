from netbox.plugins import PluginMenuItem

menu_buttons = (
    PluginMenuItem(
        link='plugins:netbox_proxmox_import:proxmoxconnection_list',
        link_text='Proxmox Connections',
    ),
)

menu_items = menu_buttons
