from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
import uuid

class User(models.Model):
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)  # Automatically updates when a record is saved

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)


class Message(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    chat_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    chat_label = models.CharField(max_length=100, blank=True, null=True)
    messages = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)  # Automatically updates when a record is saved

