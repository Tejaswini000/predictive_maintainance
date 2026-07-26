import logging
import os

_DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def configure_logging(level: str | None = None):
    """Configure application-wide logging.

    - Default level: INFO
    - Enable DEBUG when LOG_LEVEL environment variable is set to DEBUG or when
      level='DEBUG' is passed.
    - Uses consistent formatting across the app.
    """
    env_level = os.environ.get("LOG_LEVEL", "").upper()
    chosen = (level or env_level or "INFO").upper()
    numeric = getattr(logging, chosen, logging.INFO)

    # If root already configured with handlers, avoid reconfiguring
    if logging.getLogger().handlers:
        logging.getLogger().setLevel(numeric)
        return

    logging.basicConfig(level=numeric, format=_DEFAULT_FORMAT)

    # Silence noisy third-party loggers by default (but allow override via LOG_LEVEL)
    if numeric > logging.DEBUG:
        for name in ("urllib3", "botocore", "boto3", "matplotlib", "PIL", "tensorflow"):
            logging.getLogger(name).setLevel(logging.WARNING)

    logging.getLogger(__name__).debug("Logging configured. Level=%s", logging.getLevelName(numeric))
