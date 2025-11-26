import logging.config
import yaml

# Load logging config
with open('logging_config.yaml') as f:
    config = yaml.safe_load(f)
    logging.config.dictConfig(config)

# Use logger
logger = logging.getLogger('app')
logger.info("Server started")
logger.error("Something failed")