from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary using a variable key.
    Usage: {{ mydict|get_item:keyvar }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def percentage(value, total):
    """
    Calculate percentage.
    Usage: {{ part|percentage:total }}
    """
    try:
        if total == 0:
            return 0
        return round((float(value) / float(total)) * 100, 1)
    except (ValueError, TypeError):
        return 0


@register.filter
def currency_format(value):
    """
    Format number as Indian currency.
    Usage: {{ amount|currency_format }}
    """
    try:
        value = float(value)
        if value >= 10000000:  # 1 Crore
            return f"₹{value/10000000:.1f}Cr"
        elif value >= 100000:  # 1 Lakh
            return f"₹{value/100000:.1f}L"
        elif value >= 1000:
            return f"₹{value/1000:.1f}K"
        else:
            return f"₹{value:,.0f}"
    except (ValueError, TypeError):
        return "₹0"


@register.filter
def subtract(value, arg):
    """
    Subtract arg from value.
    Usage: {{ value|subtract:arg }}
    """
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

