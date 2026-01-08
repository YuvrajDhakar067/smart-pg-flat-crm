from django import template
from common.utils import get_site_settings, get_content_block, get_status_label

register = template.Library()


@register.simple_tag
def currency_symbol():
    """Get currency symbol from settings"""
    settings = get_site_settings()
    return settings.currency_symbol


@register.simple_tag
def content(key, default=""):
    """Get content block by key"""
    return get_content_block(key, default)


@register.simple_tag
def status_info(status_type, code):
    """Get status label info"""
    return get_status_label(status_type, code)

