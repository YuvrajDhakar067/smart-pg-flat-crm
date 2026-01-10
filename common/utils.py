"""
Utility functions for accessing settings and content
"""
from .models import SiteSettings, ContentBlock, StatusLabel, NotificationTemplate
import logging

logger = logging.getLogger(__name__)


def get_site_settings():
    """Get site settings (cached)"""
    try:
        settings = SiteSettings.load()
        # Ensure missing fields have defaults (in case migration not applied)
        if not hasattr(settings, 'max_properties_per_owner'):
            settings.max_properties_per_owner = 5
        if not hasattr(settings, 'max_managers_per_owner'):
            settings.max_managers_per_owner = 5
        return settings
    except Exception as e:
        # Handle database schema errors (e.g., missing columns from pending migrations)
        error_msg = str(e)
        if 'does not exist' in error_msg.lower() or 'no such column' in error_msg.lower() or 'undefinedcolumn' in error_msg.lower():
            logger.warning(f"Site settings columns missing (migration may be pending): {e}")
            # Return default settings object with all fields
            # This allows the app to work even if migration hasn't been applied yet
            settings = SiteSettings()
            settings.pk = 1
            settings.site_name = "Smart PG & Flat Management CRM"
            settings.currency_symbol = "₹"
            settings.max_properties_per_owner = 5  # Default value
            settings.max_managers_per_owner = 5  # Default value
            return settings
        else:
            logger.error(f"Error loading site settings: {e}")
            # Return default settings if error
            settings = SiteSettings()
            settings.pk = 1
            settings.site_name = "Smart PG & Flat Management CRM"
            settings.currency_symbol = "₹"
            settings.max_properties_per_owner = 5
            settings.max_managers_per_owner = 5
            return settings


def get_content_block(key, default=""):
    """Get content block by key - handles missing fields gracefully"""
    try:
        from django.db import connection
        
        # Check if image column exists
        has_image_field = False
        try:
            if 'postgresql' in connection.vendor:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='common_contentblock' 
                        AND column_name='image'
                    """)
                    has_image_field = cursor.fetchone() is not None
            elif 'sqlite' in connection.vendor:
                with connection.cursor() as cursor:
                    cursor.execute("PRAGMA table_info(common_contentblock)")
                    columns = [row[1] for row in cursor.fetchall()]
                    has_image_field = 'image' in columns
        except Exception:
            pass
        
        # Try to get the block, deferring image field if it doesn't exist
        if has_image_field:
            block = ContentBlock.objects.get(key=key, is_active=True)
        else:
            # Use defer to avoid loading image field if it doesn't exist
            try:
                block = ContentBlock.objects.defer('image', 'video_url').get(key=key, is_active=True)
            except Exception:
                # If defer fails, try without it
                block = ContentBlock.objects.get(key=key, is_active=True)
        
        return block.content
    except ContentBlock.DoesNotExist:
        return default
    except Exception as e:
        error_msg = str(e).lower()
        if 'does not exist' in error_msg or 'no such column' in error_msg or 'undefinedcolumn' in error_msg:
            # Missing column - return default gracefully
            logger.warning(f"Content block {key} column missing (migration may be pending): {e}")
            return default
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
