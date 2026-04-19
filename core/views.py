import json

from django.core.management import call_command
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.models import Item


@require_GET
def stack(request):
    items = Item.objects.filter(state=Item.State.PENDING)
    return render(request, "core/stack.html", {
        "items": items,
        "pending_count": items.count(),
        "actioned_count": Item.objects.filter(state=Item.State.ACTIONED).count(),
    })


@require_POST
def fetch(request):
    call_command("fetch_resources")
    return redirect("stack")


@require_POST
def item_action(request, item_id):
    item = get_object_or_404(Item, pk=item_id)

    content_type = request.content_type or ""
    if "application/json" in content_type:
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        action = body.get("action", "")
    else:
        action = request.POST.get("action", "")

    if action == "seen":
        item.state = Item.State.SEEN
        item.save(update_fields=["state"])
        return HttpResponse(status=204)
    elif action == "actioned":
        item.state = Item.State.ACTIONED
        item.actioned_at = timezone.now()
        item.save(update_fields=["state", "actioned_at"])
        return HttpResponse(status=204)
    elif action == "dismissed":
        item.state = Item.State.DISMISSED
        item.save(update_fields=["state"])
        return HttpResponse(status=204)
    else:
        return JsonResponse({"error": "Invalid action. Use 'seen', 'actioned', or 'dismissed'."}, status=400)
