import json
import logging
import urllib.error
import urllib.request
import uuid

from django.conf import settings

from actions.base import BaseAction

logger = logging.getLogger(__name__)


class TodoistAction(BaseAction):
    action_id = "todoist"

    def execute(self, item):
        token = settings.TODOIST_API_TOKEN
        if not token:
            return

        content = f"[{item.title}]({item.url})" if item.url else item.title
        payload = json.dumps({"content": content}).encode()
        req = urllib.request.Request(
            "https://api.todoist.com/api/v1/tasks",
            data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Request-Id": str(uuid.uuid4()),
            },
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            from core.models import ActionError
            msg = f"HTTP {e.code}" if isinstance(e, urllib.error.HTTPError) else str(e)
            logger.warning("Todoist action failed for item %s: %s", item.pk, msg)
            ActionError.objects.create(item=item, action_id=self.action_id, error=msg)
