import logging


def configure_logging(level: str) -> None:
    logging.getLogger("app").setLevel(level.upper())
