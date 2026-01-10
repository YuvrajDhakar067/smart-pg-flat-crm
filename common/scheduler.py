"""
Background task scheduler for automatic monthly rent generation.
Uses APScheduler to run tasks in the background without requiring external services.
"""
import logging
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.core.management import call_command
from django.utils import timezone

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None


def generate_monthly_rent_job():
    """
    Background job to generate monthly rent records for all active occupancies.
    Runs on the 1st of each month at 00:00 (midnight).
    """
    try:
        logger.info("Starting scheduled monthly rent generation...")
        call_command('generate_monthly_rent')
        logger.info("Scheduled monthly rent generation completed successfully")
    except Exception as e:
        logger.error(f"Error in scheduled monthly rent generation: {str(e)}", exc_info=True)


def start_scheduler():
    """
    Initialize and start the background scheduler.
    This should be called once when Django starts.
    """
    global scheduler
    
    if scheduler is not None and scheduler.running:
        logger.warning("Scheduler is already running")
        return
    
    try:
        # Create scheduler
        scheduler = BackgroundScheduler()
        
        # Get timezone from Django settings
        tz = timezone.get_current_timezone()
        
        # Schedule monthly rent generation: 1st of every month at 00:00
        scheduler.add_job(
            generate_monthly_rent_job,
            trigger=CronTrigger(
                day=1,  # First day of month
                hour=0,  # Midnight
                minute=0,
                timezone=tz
            ),
            id='generate_monthly_rent',
            name='Generate Monthly Rent Records',
            replace_existing=True,
            max_instances=1,  # Prevent overlapping runs
            coalesce=True  # Combine multiple pending executions into one
        )
        
        # Start the scheduler
        scheduler.start()
        logger.info("Background scheduler started successfully")
        logger.info(f"Monthly rent generation scheduled for 1st of each month at 00:00 ({tz})")
        
        # Register shutdown handler
        atexit.register(lambda: stop_scheduler())
        
    except Exception as e:
        logger.error(f"Failed to start scheduler: {str(e)}", exc_info=True)
        scheduler = None


def stop_scheduler():
    """
    Stop the background scheduler.
    Should be called when Django shuts down.
    """
    global scheduler
    
    if scheduler is not None and scheduler.running:
        try:
            scheduler.shutdown(wait=True)
            logger.info("Background scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {str(e)}", exc_info=True)
        finally:
            scheduler = None
