import logging
import json
import threading
from sqlalchemy.orm import Session
from database import SessionLocal
import models
import datetime

# Prevent circular imports or logger recursion
_logging_lock = threading.Lock()

class SQLAlchemyHandler(logging.Handler):
    """
    Custom Handler to write logs to SQLite.
    """
    def emit(self, record):
        # Avoid infinite recursion if DB functions logging themselves
        # But our DB code uses print() or standard logging, so just be careful.
        try:
            msg = self.format(record)
            
            # Extract structured metadata if passed as 'extra'
            # Usage: logger.info("msg", extra={"user_id": 123})
            metadata = getattr(record, "metadata", None)
            if not metadata:
                # check args if passed as dict? 
                if isinstance(record.args, dict):
                    metadata = record.args
            
            meta_json = None
            if metadata:
                try:
                    meta_json = json.dumps(metadata, default=str)
                except:
                    meta_json = str(metadata)

            log_entry = models.SystemLog(
                level=record.levelname,
                module=record.name.split(".")[-1] if "." in record.name else record.name,
                message=msg,
                metadata_json=meta_json,
                created_at=datetime.datetime.now()
            )

            # Use a separate session to ensure commit immediately
            # Using try-except block inside to not crash app on log failure
            with _logging_lock:
                db = SessionLocal()
                try:
                    db.add(log_entry)
                    db.commit()
                except Exception:
                    pass # Fail silently on logging error to prevent app crash
                finally:
                    db.close()

        except Exception:
            self.handleError(record)

def setup_logging():
    """
    Configures the root logger for the application.
    """
    # 1. Root Logger
    logger = logging.getLogger("decade_journey")
    logger.setLevel(logging.INFO)
    logger.propagate = False # Don't duplicate to uvicorn root

    # 2. Clear existing to prevent duplicates on reload
    if logger.handlers:
        logger.handlers.clear()

    # 3. Stream Handler (Console) - Colors!
    c_handler = logging.StreamHandler()
    c_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    c_handler.setFormatter(c_formatter)
    logger.addHandler(c_handler)

    # 4. DB Handler (SQLite)
    db_handler = SQLAlchemyHandler()
    # Simple message format for DB, because fields are separate
    db_formatter = logging.Formatter('%(message)s') 
    db_handler.setFormatter(db_formatter)
    logger.addHandler(db_handler)
    
    # 5. Connect Uvicorn's loggers to ours? 
    # Optional. For now let's just log our app events.
    
    logger.info("📝 Logger: Ready (Console + DB)")

def get_logger(name: str):
    """
    Returns a child logger, e.g. decade_journey.vision
    """
    return logging.getLogger(f"decade_journey.{name}")
