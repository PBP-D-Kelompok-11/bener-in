from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from authentication.models import Customer, KategoriBarang, MitraReparasi


class RepairRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        REJECTED = 'rejected', 'Rejected'
        CANCELLED = 'cancelled', 'Cancelled'
        UNABLE_TO_REPAIR = 'unable_to_repair', 'Unable to Repair'

    TRANSITIONS = {
        Status.PENDING: {
            Status.ACCEPTED: 'mitra',
            Status.REJECTED: 'mitra',
            Status.CANCELLED: 'customer',
        },
        Status.ACCEPTED: {
            Status.IN_PROGRESS: 'mitra',
            Status.UNABLE_TO_REPAIR: 'mitra',
        },
        Status.IN_PROGRESS: {
            Status.COMPLETED: 'mitra',
            Status.UNABLE_TO_REPAIR: 'mitra',
        },
    }
    REASON_REQUIRED = {Status.REJECTED, Status.UNABLE_TO_REPAIR}

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='repair_requests',
    )
    mitra = models.ForeignKey(
        MitraReparasi, on_delete=models.PROTECT,
        related_name='repair_requests',
    )
    category = models.CharField(max_length=20, choices=KategoriBarang.choices)
    item_name = models.CharField(max_length=150)
    description = models.TextField()
    submission_token = models.CharField(
        max_length=255, unique=True, null=True, blank=True, editable=False,
    )
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.PENDING, editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.item_name} — {self.get_status_display()}'

    @property
    def is_successful(self):
        return self.status == self.Status.COMPLETED

    def clean(self):
        super().clean()
        self.item_name = (self.item_name or '').strip()
        self.description = (self.description or '').strip()
        errors = {}
        if not self.item_name:
            errors['item_name'] = 'Enter an item name.'
        if not self.description:
            errors['description'] = 'Describe the repair issue.'
        if self._state.adding:
            if self.status != self.Status.PENDING:
                errors['status'] = 'New requests must start as Pending.'
            if self.mitra_id and not MitraReparasi.objects.filter(
                pk=self.mitra_id, is_active=True,
            ).exists():
                errors['mitra'] = 'Choose an active registered mitra.'
            if self.customer_id and not Customer.objects.filter(
                pk=self.customer_id, is_active=True,
            ).exists():
                errors['customer'] = 'An active customer is required.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self._state.adding:
                original = type(self).objects.select_for_update().get(pk=self.pk)
                if (self.customer_id != original.customer_id
                        or self.mitra_id != original.mitra_id
                        or self.category != original.category):
                    raise ValidationError('Customer, mitra, and category cannot change.')
                if self.status != original.status:
                    raise ValidationError('Use transition_to() to change status.')
                if original.status != self.Status.PENDING and (
                    self.item_name != original.item_name
                    or self.description != original.description
                ):
                    raise ValidationError('Only Pending requests can be edited.')
            self.full_clean()
            creating = self._state.adding
            super().save(*args, **kwargs)
            if creating:
                RepairStatusHistory.objects.create(
                    request=self,
                    from_status=None,
                    to_status=self.Status.PENDING,
                    customer_actor=self.customer,
                )

    def delete(self, *args, **kwargs):
        raise ValidationError('Cancel requests instead of deleting them.')

    def transition_to(self, to_status, actor, reason=''):
        """Change status and append its history event as one guarded transaction."""
        if self.pk is None:
            raise ValidationError('Save the request before changing its status.')
        reason = (reason or '').strip()
        with transaction.atomic():
            current = type(self).objects.select_for_update().get(pk=self.pk)
            actor_role = self.TRANSITIONS.get(current.status, {}).get(to_status)
            if actor_role is None:
                raise ValidationError('This status transition is not allowed.')
            if actor_role == 'customer':
                if not isinstance(actor, Customer) or actor.pk != current.customer_id or not actor.is_active:
                    raise ValidationError('Only the owning customer can cancel this request.')
            elif not isinstance(actor, MitraReparasi) or actor.pk != current.mitra_id or not actor.is_active:
                raise ValidationError('Only the assigned mitra can change this status.')
            if to_status in self.REASON_REQUIRED and not reason:
                raise ValidationError('A reason is required for this outcome.')

            occurred_at = timezone.now()
            changed = type(self).objects.filter(
                pk=self.pk, status=current.status,
            ).update(status=to_status, updated_at=occurred_at)
            if changed != 1:
                raise ValidationError('The request status changed. Reload and try again.')
            previous_status = current.status
            current.status = to_status
            event = RepairStatusHistory(
                request=current,
                from_status=previous_status,
                to_status=to_status,
                occurred_at=occurred_at,
                reason=reason,
                customer_actor=actor if actor_role == 'customer' else None,
                mitra_actor=actor if actor_role == 'mitra' else None,
            )
            event.save()
        self.refresh_from_db()
        return event


class RepairStatusHistory(models.Model):
    request = models.ForeignKey(
        RepairRequest, on_delete=models.PROTECT, related_name='status_history',
    )
    from_status = models.CharField(
        max_length=20, choices=RepairRequest.Status.choices,
        null=True, blank=True,
    )
    to_status = models.CharField(
        max_length=20, choices=RepairRequest.Status.choices,
    )
    occurred_at = models.DateTimeField(default=timezone.now)
    reason = models.TextField(blank=True)
    customer_actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, related_name='repair_status_events',
    )
    mitra_actor = models.ForeignKey(
        MitraReparasi, on_delete=models.PROTECT,
        null=True, blank=True, related_name='repair_status_events',
    )

    class Meta:
        ordering = ['occurred_at', 'pk']

    def clean(self):
        super().clean()
        self.reason = (self.reason or '').strip()
        errors = {}
        actor_role = (
            'customer' if self.from_status is None and self.to_status == RepairRequest.Status.PENDING
            else RepairRequest.TRANSITIONS.get(self.from_status, {}).get(self.to_status)
        )
        if actor_role is None:
            errors['to_status'] = 'This status transition is not allowed.'
        if actor_role == 'customer':
            if self.customer_actor_id is None or self.mitra_actor_id is not None:
                errors['customer_actor'] = 'A customer actor is required.'
            elif self.request_id and self.customer_actor_id != self.request.customer_id:
                errors['customer_actor'] = 'The actor must own the request.'
        elif actor_role == 'mitra':
            if self.mitra_actor_id is None or self.customer_actor_id is not None:
                errors['mitra_actor'] = 'A mitra actor is required.'
            elif self.request_id and self.mitra_actor_id != self.request.mitra_id:
                errors['mitra_actor'] = 'The actor must be the assigned mitra.'
        if self.to_status in RepairRequest.REASON_REQUIRED and not self.reason:
            errors['reason'] = 'A reason is required for this outcome.'
        if self.request_id:
            latest = type(self).objects.filter(request_id=self.request_id).order_by('-pk').first()
            if (latest.to_status if latest else None) != self.from_status:
                errors['from_status'] = 'History must follow the latest status event.'
            if self.request.status != self.to_status:
                errors['to_status'] = 'History must match the current request status.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Status history cannot be edited.')
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Status history cannot be deleted.')
