from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Review(models.Model):
    """Review customer untuk satu repair yang sudah Completed.

    Customer dan mitra tidak disimpan lagi di sini: keduanya diambil dari
    RepairRequest, jadi datanya tidak bisa tidak sinkron.
    """

    RATING_CHOICES = [
        (5, '5 - Sangat puas'),
        (4, '4 - Puas'),
        (3, '3 - Cukup'),
        (2, '2 - Kurang'),
        (1, '1 - Buruk'),
    ]

    repair_request = models.OneToOneField(
        'repair.RepairRequest', on_delete=models.CASCADE, related_name='review',
    )
    rating = models.PositiveSmallIntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(blank=True, max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.repair_request.item_name} - {self.rating}/5'

    @property
    def customer(self):
        return self.repair_request.customer

    @property
    def mitra(self):
        return self.repair_request.mitra

    @property
    def stars(self):
        return '★' * self.rating + '☆' * (5 - self.rating)

    def clean(self):
        super().clean()
        self.comment = (self.comment or '').strip()
        if self.repair_request_id and not self.repair_request.is_successful:
            raise ValidationError(
                'Review hanya bisa diberikan untuk repair yang sudah Completed.'
            )