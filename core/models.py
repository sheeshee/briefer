from django.conf import settings
from django.db import models


class Item(models.Model):

    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        SEEN = "seen", "Seen"
        ACTIONED = "actioned", "Actioned"
        DISMISSED = "dismissed", "Dismissed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="items"
    )
    source = models.CharField(max_length=50)
    external_id = models.CharField(max_length=255)
    title = models.TextField()
    summary = models.TextField(blank=True)
    url = models.URLField(blank=True)
    metadata = models.JSONField(default=dict)
    fetched_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    state = models.CharField(
        max_length=20,
        choices=State,
        default=State.PENDING,
    )
    actioned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fetched_at"]
        unique_together = ("user", "external_id")

    def __str__(self):
        return f"[{self.source}] {self.title}"


class ActionError(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="action_errors")
    action_id = models.CharField(max_length=50)
    error = models.TextField()
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]

    def __str__(self):
        return f"[{self.action_id}] {self.error[:60]}"
