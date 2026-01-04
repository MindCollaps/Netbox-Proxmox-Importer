from django.core.management.base import BaseCommand
from netbox_proxmox_import.models import ProxmoxConnection
from netbox_proxmox_import.api.sync import sync_cluster
import logging
import sys

class Command(BaseCommand):
    help = 'Sync Proxmox Clusters'

    def add_arguments(self, parser):
        parser.add_argument('--connection', type=int, help='ID of the ProxmoxConnection to sync')

    def handle(self, *args, **options):
        # Configure logging to stdout for this command
        logger = logging.getLogger('netbox_proxmox_import')
        logger.setLevel(logging.DEBUG)
        
        # Check if handler already exists to avoid duplicates
        if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        if options['connection']:
            connections = ProxmoxConnection.objects.filter(pk=options['connection'])
        else:
            connections = ProxmoxConnection.objects.all()

        if not connections.exists():
            self.stdout.write(self.style.WARNING("No Proxmox connections found."))
            return

        for connection in connections:
            self.stdout.write(f"Syncing connection: {connection} (ID: {connection.pk})")
            try:
                sync_cluster(connection.pk)
                self.stdout.write(self.style.SUCCESS(f"Successfully synced connection {connection.pk}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to sync connection {connection.pk}: {e}"))
