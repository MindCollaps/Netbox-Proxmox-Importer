from netbox.api.routers import NetBoxRouter
from django.urls import path
from . import views

app_name = 'netbox_proxmox_import'

router = NetBoxRouter()
router.register('proxmox-connections', views.ProxmoxConnectionViewSet)

urlpatterns = router.urls

urlpatterns += (
    path('sync/<int:connection_id>', views.Sync.as_view(), name="sync"),
)
