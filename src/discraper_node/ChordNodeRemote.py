from pathlib import Path
from xmlrpc.client import ServerProxy

from ._IdComparable import IdComparable
from .custom_xrpc import DiSTransport
from .custom_logger import get_logger

logger = get_logger(__name__)


class RemoteChordNode(ServerProxy, IdComparable):
    @staticmethod
    def make_remote_node(address):
        folder = Path.cwd()
        cryptoname = 'cert'
        keypair_path = folder / f"{cryptoname}.crt", folder / f"{cryptoname}.key"
        ca_path = folder / f"ca.crt"
        if keypair_path[0].exists() and keypair_path[1].exists() and ca_path.exists():
            n0 = RemoteChordNode(address, transport=DiSTransport(keypair=keypair_path,ca_file=ca_path))
        else:
            n0 = RemoteChordNode(address, transport=DiSTransport())
        return n0

    @staticmethod
    def unmarshall(val: dict):
        addr = val.get("Address", None)
        res = RemoteChordNode.make_remote_node(addr)
        return res

    def __init__(self, addr, transport=None, encoding=None, verbose=False,
                 allow_none=False, use_datetime=False, use_builtin_types=False,
                 *, headers=(), context=None):

        if hasattr(transport,"context") and transport.context is not None:
            uri = "https://" + addr[0] + ":" + str(addr[1])
        else:
            uri = "http://" +  addr[0] + ":" + str(addr[1])

        ServerProxy.__init__(self, uri, transport, encoding, verbose, allow_none, use_datetime,
                             use_builtin_types,
                             headers=headers,
                             context=context)
        super(IdComparable).__init__()
        self.Address = addr
        self.id: int = IdComparable.hasher(f"{self.Address[0]}:{self.Address[1]}")  # salty :

    def __getattr__(self, item: str):
        res = self.__dict__.get(item, None)
        if res is None:
            if item.startswith("__") and item.endswith("__"):
                raise AttributeError(f"{item}")
            res = ServerProxy.__getattr__(self, item)
            logger.debug(f"XMLCall to {item} in {self}")
        return res

    def __repr__(self):
        res = super(RemoteChordNode, self).__repr__()
        return res  # + " " + str(self.id)
