import json

from django.core.management import call_command
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from actions.todoist import TodoistAction
from core.models import ActionError, Item

_ACTIONED_ACTIONS = [TodoistAction()]


@require_GET
def stack(request):
    items = Item.objects.filter(state=Item.State.PENDING)
    return render(request, "core/stack.html", {
        "items": items,
        "pending_count": items.count(),
        "actioned_count": Item.objects.filter(state=Item.State.ACTIONED).count(),
    })


@require_GET
def history(request):
    items = Item.objects.order_by("-fetched_at")
    paginator = Paginator(items, 50)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "core/history.html", {"page": page})


@require_POST
def reset(request):
    Item.objects.exclude(state=Item.State.PENDING).update(state=Item.State.PENDING, actioned_at=None)
    return redirect("stack")


@require_POST
def fetch(request):
    include_fake = bool(request.POST.get("include_fake"))
    call_command("fetch_resources", include_fake=include_fake)
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
        for act in _ACTIONED_ACTIONS:
            act.execute(item)
        return HttpResponse(status=204)
    elif action == "dismissed":
        item.state = Item.State.DISMISSED
        item.save(update_fields=["state"])
        return HttpResponse(status=204)
    else:
        return JsonResponse({"error": "Invalid action. Use 'seen', 'actioned', or 'dismissed'."}, status=400)


@require_GET
def action_errors(request):
    errors = ActionError.objects.select_related("item").order_by("-occurred_at")
    paginator = Paginator(errors, 50)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "core/action_errors.html", {"page": page})


@require_GET
def action_error_detail(request, error_id):
    error = get_object_or_404(ActionError, pk=error_id)
    return render(request, "core/action_error_detail.html", {"error": error})
