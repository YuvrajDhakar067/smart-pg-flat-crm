from django.apps import AppConfig
import logging
import os

logger = logging.getLogger(__name__)


class CommonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'common'
    
    def ready(self):
        """
        Initialize background scheduler when Django app is ready.
        Only start scheduler in the main process (not in migrations, tests, or worker processes).
        """
        # Skip if running migrations, tests, or in a subprocess
        if os.environ.get('RUN_MAIN') != 'true':
            return
        
        # Skip if running management commands (except runserver)
        import sys
        if len(sys.argv) > 1 and sys.argv[1] in ['migrate', 'makemigrations', 'test', 'collectstatic']:
            return
        
        # Check if scheduler should be enabled (default: True)
        from django.conf import settings
        enable_scheduler = getattr(settings, 'ENABLE_BACKGROUND_SCHEDULER', True)
        
        if enable_scheduler:
            try:
                from .scheduler import start_scheduler
                start_scheduler()
                logger.info("Background task scheduler initialized")
            except ImportError as e:
                # Silently skip if APScheduler is not installed (e.g., in development)
                logger.warning(f"Scheduler module not available (APScheduler not installed): {e}")
            except Exception as e:
                logger.error(f"Failed to initialize scheduler: {str(e)}", exc_info=True)

