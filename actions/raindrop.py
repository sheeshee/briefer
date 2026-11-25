"""Save actioned items to Raindrop.io.

Auth is OAuth2 (https://developer.raindrop.io/v1/authentication/token):
/raindrop/connect/ sends the browser to Raindrop, /raindrop/callback/ swaps the
code for tokens, stored in RaindropToken. Access tokens expire after two weeks
and are refreshed here before use. RAINDROP_TEST_TOKEN, if set, skips all that.
"""
import logging
from datetime import timedelta
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.utils import timezone

from actions.base import BaseAction
from core.models import ActionError, RaindropToken

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://raindrop.io/oauth/authorize"
TOKEN_URL = "https://raindrop.io/oauth/access_token"
CREATE_URL = "https://api.raindrop.io/rest/v1/raindrop"
REFRESH_MARGIN = timedelta(days=1)
TIMEOUT = 10


class RaindropError(Exception):
    pass


class MissingURL(RaindropError):
    """Not a fault: some items just have nothing to bookmark."""


def is_configured():
    return bool(settings.RAINDROP_TEST_TOKEN or settings.RAINDROP_CLIENT_ID)


def is_connected():
    return bool(settings.RAINDROP_TEST_TOKEN) or RaindropToken.objects.filter(pk=1).exists()


def authorize_url():
    return AUTHORIZE_URL + "?" + urlencode({
        "client_id": settings.RAINDROP_CLIENT_ID,
        "redirect_uri": settings.RAINDROP_REDIRECT_URI,
        "response_type": "code",
    })


def _store(data):
    token, _ = RaindropToken.objects.update_or_create(pk=1, defaults={
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_at": timezone.now() + timedelta(seconds=int(data["expires_in"])),
    })
    return token


def _token_request(body):
    resp = requests.post(TOKEN_URL, json=body, timeout=TIMEOUT)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        raise RaindropError(f"token request failed: HTTP {resp.status_code}") from e
    return _store(resp.json())


def exchange_code(code):
    return _token_request({
        "grant_type": "authorization_code",
        "code": code,
        "client_id": settings.RAINDROP_CLIENT_ID,
        "client_secret": settings.RAINDROP_CLIENT_SECRET,
        "redirect_uri": settings.RAINDROP_REDIRECT_URI,
    })


def access_token():
    if settings.RAINDROP_TEST_TOKEN:
        return settings.RAINDROP_TEST_TOKEN
    token = RaindropToken.objects.filter(pk=1).first()
    if token is None:
        raise RaindropError("Raindrop not connected: open /raindrop/connect/")
    if token.expires_at - timezone.now() < REFRESH_MARGIN:
        token = _token_request({
            "client_id": settings.RAINDROP_CLIENT_ID,
            "client_secret": settings.RAINDROP_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
        })
    return token.access_token


class RaindropAction(BaseAction):
    action_id = "raindrop"

    def execute(self, item):
        if not is_configured():
            return
        try:
            if not item.url:
                raise MissingURL("item has no URL to bookmark")
            body = {
                "link": item.url,
                "title": item.title,
                "tags": ["briefer"],
                "pleaseParse": {},
            }
            if settings.RAINDROP_COLLECTION_ID:
                body["collection"] = {"$id": int(settings.RAINDROP_COLLECTION_ID)}
            resp = requests.post(
                CREATE_URL,
                json=body,
                headers={"Authorization": f"Bearer {access_token()}"},
                timeout=TIMEOUT,
            )
            if resp.status_code >= 400:
                raise RaindropError(f"HTTP {resp.status_code}")
        except Exception as e:
            # ERROR reaches the OpenObserve app_errors alert (ntfy); a lost
            # bookmark or a dead token needs Sam's attention.
            level = logging.WARNING if isinstance(e, MissingURL) else logging.ERROR
            logger.log(level, "Raindrop action failed for item %s: %s", item.pk, e)
            ActionError.objects.create(item=item, action_id=self.action_id, error=str(e))
