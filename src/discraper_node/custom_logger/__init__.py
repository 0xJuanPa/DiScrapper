from logging import StreamHandler, Logger, getLogger, DEBUG

from .CustomLogger import LoggerColorFormatter as _LoggerColorFormatter


def get_logger(name) -> Logger:
    logger = getLogger(name)
    logger.propagate = False
    # create console handler with a higher log level
    ch = StreamHandler()
    ch.setLevel(DEBUG)
    ch.setFormatter(_LoggerColorFormatter())
    logger.addHandler(ch)
    return logger
