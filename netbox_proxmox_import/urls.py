from django.urls import path
from . import views, models
from netbox.views.generic import ObjectChangeLogView

urlpatterns = (
    path('proxmox-connections/', views.ProxmoxConnectionListView.as_view(), name='proxmoxconnection_list'),
    path('proxmox-connections/add', views.ProxmoxConnectionEditView.as_view(), name='proxmoxconnection_add'),
    path('proxmox-connections/<int:pk>', views.ProxmoxConnectionView.as_view(), name='proxmoxconnection'),
    path('proxmox-connections/<int:pk>/edit', views.ProxmoxConnectionEditView.as_view(), name='proxmoxconnection_edit'),
    path('proxmox-connections/<int:pk>/delete', views.ProxmoxConnectionDeleteView.as_view(), name='proxmoxconnection_delete'),

    path('proxmox-connections/<int:pk>/changelog', ObjectChangeLogView.as_view(), name='proxmoxconnection_changelog', kwargs={
        'model': models.ProxmoxConnection
    }),
)


