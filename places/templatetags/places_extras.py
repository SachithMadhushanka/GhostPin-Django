# places/templatetags/places_extras.py
@register.filter
def lte(value, arg):
    return value <= arg