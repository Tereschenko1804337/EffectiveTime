from django.db import models
from user.models import User


class Category(models.Model):
    name = models.CharField(max_length=63)
    user = models.ForeignKey(User , on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "category"