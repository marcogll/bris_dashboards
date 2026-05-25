"""Señales para auditoría de solicitudes.

Crea registros de auditoría cuando se crea o modifica una solicitud.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Request, RequestComment


@receiver(pre_save, sender=Request)
def request_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = Request.objects.get(pk=instance.pk)
            instance._old_estatus = old.estatus
        except Request.DoesNotExist:
            pass


@receiver(post_save, sender=Request)
def request_post_save(sender, instance, created, **kwargs):
    if not created and hasattr(instance, '_old_estatus') and instance._old_estatus != instance.estatus:
        RequestComment.objects.create(
            request=instance,
            author=None,
            contenido=f'Estatus cambiado: {instance._old_estatus} → {instance.estatus}',
        )


@receiver(post_save, sender=RequestComment)
def request_comment_post_save(sender, instance, created, **kwargs):
    if created:
        from core.models import NotificationLog
        NotificationLog.objects.create(
            tipo='telegram',
            destinatario=f'request_{instance.request_id}',
            mensaje=f'Comentario en solicitud #{instance.request_id}: {instance.contenido[:100]}',
            estatus='sent',
        )