from netbox.api.viewsets import NetBoxModelViewSet

from django.http import HttpResponse
from django.views import View
from django.contrib.auth.mixins import PermissionRequiredMixin
import logging
import json

from .. import models
from .serializers import ProxmoxConnectionSerializer
from .sync import sync_cluster

logger = logging.getLogger(__name__)

class ProxmoxConnectionViewSet(NetBoxModelViewSet):
    queryset = models.ProxmoxConnection.objects.prefetch_related('tags')
    serializer_class = ProxmoxConnectionSerializer



class Sync(PermissionRequiredMixin, View):
    permission_required = "nbp_sync.sync_proxmox_cluster"

    def post(self, _, connection_id):
        try:
            json_result = sync_cluster(connection_id)
            return HttpResponse(
                json_result, status=200, content_type='application/json'
            )
        except Exception as e:
            logger.exception(f"Error syncing Proxmox cluster {connection_id}")
            return HttpResponse(
                json.dumps({"error": str(e)}), status=500, content_type='application/json'
            )
