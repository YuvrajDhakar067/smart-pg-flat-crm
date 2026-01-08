"""
Utility functions for accessing settings and content
"""
from .models import SiteSettings, ContentBlock, StatusLabel, NotificationTemplate
from django.core.exceptions import ObjectDoesNotExist
import logging

logger = logging.getLogger(__name__)


def get_site_settings():
    """Get site settings (cached)"""
    try:
        return SiteSettings.load()
    except Exception as e:
        logger.error(f"Error loading site settings: {e}")
        # Return default settings if error
        return SiteSettings(
            site_name="Smart PG & Flat Management CRM",
            currency_symbol="₹"
        )


def get_content_block(key, default=""):
    """Get content block by key"""
    try:
        block = ContentBlock.objects.get(key=key, is_active=True)
        return block.content
    except ContentBlock.DoesNotExist:
        return default
    except Exception as e:
        logger.error(f"Error loading content block {key}: {e}")
        return default


def get_status_label(status_type, code, default=None):
    """Get status label for a given type and code"""
    try:
        label = StatusLabel.objects.get(status_type=status_type, code=code, is_active=True)
        return {
            'label': label.label,
            'color': label.color,
            'icon': label.icon,
        }
    except StatusLabel.DoesNotExist:
        if default:
            return default
        return {
            'label': code.title(),
            'color': '#64748b',
            'icon': '',
        }
    except Exception as e:
        logger.error(f"Error loading status label {status_type}/{code}: {e}")
        return {
            'label': code.title(),
            'color': '#64748b',
            'icon': '',
        }


def get_notification_template(template_type):
    """Get notification template"""
    try:
        return NotificationTemplate.objects.get(template_type=template_type, is_active=True)
    except NotificationTemplate.DoesNotExist:
        return None
    except Exception as e:
        logger.error(f"Error loading notification template {template_type}: {e}")
        return None


def format_notification_message(template, context):
    """Format notification message with context variables"""
    if not template:
        return ""
    
    try:
        message = template.message
        for key, value in context.items():
            message = message.replace(f"{{{{{key}}}}}", str(value))
        return message
    except Exception as e:
        logger.error(f"Error formatting notification message: {e}")
        return ""


def validate_account_access(user, account):
    """
    Validate that user has access to the account
    Returns (is_valid, error_message)
    """
    if not user.is_authenticated:
        return False, "User not authenticated"
    
    if not hasattr(user, 'account'):
        return False, "User account not configured"
    
    if user.account.id != account.id:
        return False, "Access denied: Account mismatch"
    
    if not hasattr(user, 'role') or user.role not in ['OWNER', 'MANAGER']:
        return False, "Access denied: Insufficient permissions"
    
    return True, None
