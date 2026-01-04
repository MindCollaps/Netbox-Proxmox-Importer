from django.db import models
from django.urls import reverse
from netbox.models import NetBoxModel

from django.db.models import IntegerField, Model
from django.core.validators import MaxValueValidator, MinValueValidator



class ProxmoxConnection(NetBoxModel):

    def get_absolute_url(self):
        return reverse('plugins:netbox_proxmox_import:proxmoxconnection', args=[self.pk])

    def __str__(self):
        return f'{self.cluster} (Proxmox)'

    domain = models.CharField(max_length=255)
    port = IntegerField(validators=[
        MaxValueValidator(65535),
        MinValueValidator(1)
    ])
    verify_ssl = models.BooleanField(default=True)

    user = models.CharField(max_length=127)

    token_id = models.CharField(max_length=127)
    token_secret = models.CharField(max_length=127)

    cluster = models.ForeignKey(
        to='virtualization.cluster',
        on_delete=models.CASCADE,
        related_name='connections'
    )
