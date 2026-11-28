from django import template

from resources.claude_usage import render_chart

register = template.Library()


@register.simple_tag
def claude_usage_chart(metadata):
    return render_chart(metadata)
