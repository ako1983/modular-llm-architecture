# logging_config.py
import logging
import os


def setup_logger(name):
    # Define log directory and file
    log_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "output", "log"
    )
    log_file_path = os.path.join(log_dir, "mylog.log")
    os.makedirs(log_dir, exist_ok=True)

    # Set up logging
    logging.basicConfig(
        filename=log_file_path,
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(name)
    return logger
