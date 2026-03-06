# places/templatetags/trail_tags.py
from django import template
from places.models import TrailPlace, CheckIn

register = template.Library()

@register.simple_tag(takes_context=True)
def user_trail_progress(context, trail):
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return None

    place_ids = TrailPlace.objects.filter(
        id=trail.id
    ).values_list('place_id', flat=True)

    total = len(place_ids)
    if total == 0:
        return None
    
    completed = CheckIn.objects.filter(
        user=request.user,
        place_id__in=place_ids
    ).values('place_id').distinct().count()
    
    return {
        'total': total,
        'completed': completed,
        'percent': round((completed / total) * 100),
    }