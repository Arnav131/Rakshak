"""
railway/signals.py
Audits logins/logouts and every user-driven model change into AuditLog.
Runs only for authenticated web requests (seed commands skip it).
"""
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
import logging

from .middleware import get_current_user
from .models import (
    AuditLog, Zone, Division, Station, TrackSection, Asset,
    SensorType, Sensor, SensorCalibration, SensorReading,
    Alert, AlertEscalation, MaintenanceTeam, Ticket, TicketStatusLog,
    MLModel, MLModelRun, AnomalyPrediction,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Models to audit — add new models here to automatically track changes
# ---------------------------------------------------------------------------
AUDITED_MODELS = [
    Zone, Division, Station, TrackSection, Asset,
    SensorType, Sensor, SensorCalibration, SensorReading,
    Alert, AlertEscalation, MaintenanceTeam, Ticket, TicketStatusLog,
    MLModel, MLModelRun, AnomalyPrediction,
]

# Models that trigger STATUS_CHANGE when their 'status' field changes
STATUS_MODELS = (Alert, Ticket)


def _snapshot(instance):
    """
    Create a JSON-safe snapshot of an instance's field values.
    Excludes non-serializable fields and handles exceptions gracefully.
    """
    data = {}
    for field in instance._meta.concrete_fields:
        try:
            value = getattr(instance, field.name)
            # Handle special types for JSON serialization
            if hasattr(value, 'isoformat'):  # datetime/date
                data[field.name] = value.isoformat()
            elif hasattr(value, 'pk'):  # ForeignKey
                data[field.name] = str(value.pk)
            else:
                data[field.name] = str(value)
        except Exception as e:
            logger.warning(f"Could not snapshot {instance._meta.model_name}.{field.name}: {e}")
            data[field.name] = None
    return data


@receiver(user_logged_in)
def audit_login(sender, request, user, **kwargs):
    """Log user login events."""
    if not user:
        return
    AuditLog.objects.create(
        event_type=AuditLog.EventType.LOGIN,
        entity_type='user',
        entity_id=str(user.pk),
        actor_type=AuditLog.ActorType.USER,
        actor_identifier=user.username,
        description=f'User {user.username} logged in.',
        # Add metadata for better tracking
        new_state={'ip': getattr(request, 'META', {}).get('REMOTE_ADDR', 'unknown')}
    )


@receiver(user_logged_out)
def audit_logout(sender, request, user, **kwargs):
    """Log user logout events."""
    if not user:
        return
    AuditLog.objects.create(
        event_type=AuditLog.EventType.LOGOUT,  # Fixed: was LOGIN, should be LOGOUT
        entity_type='user',
        entity_id=str(user.pk),
        actor_type=AuditLog.ActorType.USER,
        actor_identifier=user.username,
        description=f'User {user.username} logged out.',
    )


@receiver(pre_save)
def audit_pre_save(sender, instance, **kwargs):
    """Snapshot the instance before save for comparison."""
    if sender not in AUDITED_MODELS:
        return
    
    # Skip raw saves (like loaddata)
    if kwargs.get('raw', False):
        return
    
    if instance.pk:
        try:
            previous = sender.objects.get(pk=instance.pk)
            instance._audit_previous = _snapshot(previous)
        except sender.DoesNotExist:
            instance._audit_previous = {}
    else:
        instance._audit_previous = {}


@receiver(post_save)
def audit_post_save(sender, instance, created, **kwargs):
    """Log create/update/status-change events after save."""
    if sender not in AUDITED_MODELS:
        return
    
    # Skip raw saves
    if kwargs.get('raw', False):
        return
    
    user = get_current_user()
    if not user or not user.is_authenticated:
        return
    
    previous = getattr(instance, '_audit_previous', {})
    new_state = _snapshot(instance)

    if created:
        event_type = AuditLog.EventType.CREATE
    elif isinstance(instance, STATUS_MODELS) and previous.get('status') != new_state.get('status'):
        event_type = AuditLog.EventType.STATUS_CHANGE
    else:
        event_type = AuditLog.EventType.UPDATE

    # Only create audit log if something actually changed
    if not created and previous == new_state:
        return

    try:
        AuditLog.objects.create(
            event_type=event_type,
            entity_type=instance._meta.model_name,
            entity_id=str(instance.pk),
            actor_type=AuditLog.ActorType.USER,
            actor_identifier=user.username,
            previous_state=previous,
            new_state=new_state,
            description=f'{user.username} {event_type} {instance._meta.model_name}:{instance.pk}',
        )
    except Exception as e:
        # Log but don't break the save operation
        logger.error(f"Failed to create audit log: {e}")


@receiver(post_delete)
def audit_post_delete(sender, instance, **kwargs):
    """Log delete events."""
    if sender not in AUDITED_MODELS:
        return
    
    user = get_current_user()
    if not user or not user.is_authenticated:
        return
    
    try:
        AuditLog.objects.create(
            event_type=AuditLog.EventType.DELETE,
            entity_type=instance._meta.model_name,
            entity_id=str(instance.pk),
            actor_type=AuditLog.ActorType.USER,
            actor_identifier=user.username,
            previous_state=_snapshot(instance),
            description=f'{user.username} deleted {instance._meta.model_name}:{instance.pk}',
        )
    except Exception as e:
        logger.error(f"Failed to create delete audit log: {e}")