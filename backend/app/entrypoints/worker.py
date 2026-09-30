import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Worker started (placeholder loop)")
    while True:
        time.sleep(60)
