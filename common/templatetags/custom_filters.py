"""
Custom template filters for the application
"""
from django import template

register = template.Library()


@register.filter
def mul(value, arg):
    """
    Multiply the value by the arg
    Usage: {{ value|mul:10 }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def div(value, arg):
    """
    Divide the value by the arg
    Usage: {{ value|div:100 }}
    """
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter(name='abs')
def abs_filter(value):
    """
    Return the absolute value
    Usage: {{ value|abs }}
    """
    try:
        return abs(float(value))
    except (ValueError, TypeError):
        return 0

