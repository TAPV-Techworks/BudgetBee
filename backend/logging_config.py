import logging
import pytz
from datetime import datetime

class ISTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        # Convert the timestamp to IST
        ist_timezone = pytz.timezone('Asia/Kolkata')
        record_time = datetime.fromtimestamp(record.created, ist_timezone)
        return record_time.strftime(datefmt) if datefmt else record_time.isoformat()

def setup_logging():
    logger = logging.getLogger()
    if not logger.handlers:
        formatter = ISTFormatter(
            fmt='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

    return logger
