from django.contrib.auth.models import AbstractUser
from django.db import models
from datetime import time


class User(AbstractUser):
    photo_url = models.URLField(null=True, default=None, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    tg_id = models.BigIntegerField(null=True, blank=True, unique=True, db_index=True)
    wake_up_time = models.TimeField(default=time(8, 0))
    bed_time = models.TimeField(default=time(23, 0))
    theme = models.CharField(max_length=10, default='dark', choices=[('dark', 'Dark'), ('light', 'Light')])

    def __str__(self):
        return self.username
