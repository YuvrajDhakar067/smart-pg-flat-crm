"""
Logging configuration with request ID support
"""
import logging
import uuid
from django.utils.log import RequireDebugFalse


class RequestIDFilter(logging.Filter):
    """
    Logging filter to add request ID to log records
    """
    def filter(self, record):
        # Get request ID from record if available
        request_id = getattr(record, 'request_id', None)
        if not request_id:
            # Try to get from thread local if available
            try:
                from threading import local
                thread_local = getattr(logging, '_thread_local', None)
                if thread_local:
                    request_id = getattr(thread_local, 'request_id', None)
            except Exception:
                pass
        
        record.request_id = request_id or 'N/A'
        return True


class RequestIDMiddleware:
    """
    Middleware to generate and attach unique request ID to each request.
    Request ID is available in request.request_id and in all log messages.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Set up thread-local storage for request ID
        import threading
        if not hasattr(logging, '_thread_local'):
            logging._thread_local = threading.local()
    
    def __call__(self, request):
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]  # Short 8-character ID
        request.request_id = request_id
        
        # Store in thread-local for logging
        logging._thread_local.request_id = request_id
        
        # Add to response headers for debugging
        response = self.get_response(request)
        response['X-Request-ID'] = request_id
        
        # Clean up thread-local
        try:
            delattr(logging._thread_local, 'request_id')
        except AttributeError:
            pass
        
        return response
    
    def process_exception(self, request, exception):
        """Log exceptions with request ID"""
        request_id = getattr(request, 'request_id', 'N/A')
        logger = logging.getLogger('django.request')
        logger.error(
            f"[{request_id}] Exception: {type(exception).__name__}: {str(exception)}",
            exc_info=True,
            extra={'request_id': request_id}
        )

