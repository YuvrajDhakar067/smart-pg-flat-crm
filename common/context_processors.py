"""
Context processors to make settings available in all templates
"""
from .utils import get_site_settings, get_content_block


def site_settings(request):
    """Add site settings to template context"""
    return {
        'site_settings': get_site_settings(),
    }


def content_blocks(request):
    """Add commonly used content blocks to context"""
    return {
        'dashboard_welcome': get_content_block('dashboard_welcome', 'Welcome to your property management dashboard!'),
        'vacancy_alert': get_content_block('vacancy_alert', 'You have vacant units. Fill them to maximize revenue!'),
    }

