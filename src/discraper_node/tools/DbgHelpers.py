import os
import time
from multiprocessing.connection import Client
import logging
from ..custom_logger import get_logger

logger = get_logger(__name__)


class DeuggableIdAdrr:
    def __init__(self, value):
        self.id = value.id
        adrr = value.Address
        if isinstance(adrr, tuple):
            adrr = list(adrr)
        elif isinstance(adrr, str):
            adrr = [adrr]
        self.addr = adrr

    def __repr__(self):
        return f"({':'.join(map(str, self.addr))})"


def debug_d(self):
    debug = 'DEBUG'
    if debug in os.environ:
        logging.basicConfig(level=logging.DEBUG)
        logger.info(f"{debug} mode")

        dbgstr = os.environ.get(debug, "127.0.0.1:6000")
        ip, port = dbgstr.split(":")
        port = int(port)
        print(f"Connecting to debug server... {ip}:{port}")
        while True:
            try:
                with Client((ip, port)) as client:
                    fing = list(map(lambda e: None if e is None else DeuggableIdAdrr(e), self.finger))
                    rsucc = list(map(lambda e: None if e is None else DeuggableIdAdrr(e), self.r_successors))
                    doc = list(map(lambda e: None if e is None else DeuggableIdAdrr(e), self.database))
                    client.send(
                        (DeuggableIdAdrr(self), DeuggableIdAdrr(self.Predecessor()), DeuggableIdAdrr(self.Successor()),
                         fing, rsucc, doc))
            except Exception as e:
                logger.debug(f"Debug thread failed {e}")
            time.sleep(2)
