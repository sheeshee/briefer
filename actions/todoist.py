"""Create a Todoist task, due today, from an item (used by the Claude usage card)."""
import logging
import uuid

import requests
from django.conf import settings

from actions.base import BaseAction
from core.models import ActionError

logger = logging.getLogger(__name__)

TASKS_URL = "https://api.todoist.com/api/v1/tasks"
TIMEOUT = 10


class TodoistAction(BaseAction):
    action_id = "todoist"

    def __init__(self, content: str):
        self.content = content

    def execute(self, item):
        try:
            token = settings.TODOIST_API_TOKEN
            if not token:
                raise RuntimeError("TODOIST_API_TOKEN is not set")
            content = f"[{self.content}]({item.url})" if item.url else self.content
            resp = requests.post(
                TASKS_URL,
                json={"content": content, "due_string": "today"},
                headers={"Authorization": f"Bearer {token}", "X-Request-Id": str(uuid.uuid4())},
                timeout=TIMEOUT,
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}")
        except Exception as e:
            # ERROR reaches the OpenObserve app_errors alert (ntfy).
            logger.error("Todoist action failed for item %s: %s", item.pk, e)
            ActionError.objects.create(item=item, action_id=self.action_id, error=str(e))
