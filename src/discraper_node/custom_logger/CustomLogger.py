from logging import Formatter, INFO, DEBUG, WARNING, ERROR, CRITICAL


# logging.basicConfig(level=logging.DEBUG) # to log all dependencies

# class CustomAdapter(logging.LoggerAdapter):
#     def process(self, msg, kwargs):
#         return f"{threading.current_thread().name} {msg}", kwargs
# # logger = CustomAdapter(logger)

class LoggerColorFormatter(Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    green = "\x1b[32;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    #    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    format = "%(levelname)s: %(threadName)s - %(message)s"

    FORMATS = {
        DEBUG: grey + format + reset,
        INFO: green + format + reset,
        WARNING: yellow + format + reset,
        ERROR: red + format + reset,
        CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = Formatter(log_fmt)
        return formatter.format(record)
