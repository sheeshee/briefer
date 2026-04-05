from django.db import models


class Item(models.Model):

    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        SEEN = "seen", "Seen"
        ACTIONED = "actioned", "Actioned"
        DISMISSED = "dismissed", "Dismissed"

    source = models.CharField(max_length=50)
    external_id = models.CharField(max_length=255, unique=True)
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

    def __str__(self):
        return f"[{self.source}] {self.title}"
