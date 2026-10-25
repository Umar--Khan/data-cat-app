import logging
from typing import Literal

type LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: LogLevel) -> None:
    """Send catalogue logs at `level` to stderr and keep third-party libraries at WARNING.

    Uvicorn configures its own loggers without propagation, so its lines are not duplicated.
    """
    logging.basicConfig(level=logging.WARNING, format=_FORMAT)
    logging.getLogger("catalogue").setLevel(level)
