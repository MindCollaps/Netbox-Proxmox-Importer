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
        'sync_interval': 3600, # 0 means disabled. Set to seconds (e.g. 3600 for 1 hour)
    }

    def ready(self):
        super().ready()
        try:
            import datetime
            from django.conf import settings
            from django_rq import get_scheduler
            from netbox_proxmox_import.api.sync import sync_all
            
            config = settings.PLUGINS_CONFIG.get('netbox_proxmox_import', {})
            interval = config.get('sync_interval', 0)
            
            if interval > 0:
                scheduler = get_scheduler('default')
                # Check if job already exists to avoid duplicates
                # Note: This is a simple check. For robust scheduling, might need more logic.
                # We use a specific ID for the job
                job_id = 'netbox_proxmox_import_sync_all'
                
                # Cancel existing job if interval changed or just to be safe
                # Note: 'in scheduler' check might not work as expected for all backends, 
                # but cancel() usually handles non-existent jobs gracefully or we catch it.
                try:
                    scheduler.cancel(job_id)
                except:
                    pass
                
                # Schedule new job
                scheduler.schedule(
                    scheduled_time=datetime.datetime.utcnow(), # Start immediately-ish
                    func=sync_all,
                    interval=interval,
                    repeat=None, # Infinite
                    id=job_id
                )
        except ImportError:
            pass
        except Exception:
            # Don't crash NetBox if scheduling fails
            pass

config = NetBoxAccessListsConfig
