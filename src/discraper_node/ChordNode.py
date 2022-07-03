import logging
import math
import os
from pathlib import Path
import threading
import time

from ._IdComparable import IdComparable
from .custom_xrpc import RedirectNodeResponse, ThreadedXRPCServer, register_type_unmarshaller
from .ChordNodeRemote import RemoteChordNode
from .InfoContainer import InfoContainer
from .tools.OrderedUniqueList import OrderedUniqueList
from .tools.utils import between
from .tools.DbgHelpers import debug_d
from . import custom_logger as CustomLogger


class ChordNode(IdComparable):

    @staticmethod
    def unmarshall(val: dict):
        addr = val.get("Address", None)
        res = RemoteChordNode.make_remote_node(addr)
        return res

    def __init__(self, port=4440, interface="127.0.0.1", *, logger=None, keypair=None, ca_file=None, iterative=True,
                 aditional_types=None):
        # param validation and primitives
        assert interface != "0.0.0.0"  # only allow one interface, it does not make sense for the id
        super(IdComparable, self).__init__()
        self.Address = interface, port  # resolve public ip if have upnp or dmz
        self.id: int = IdComparable.hasher(f"{self.Address[0]}:{self.Address[1]}")  # salty :
        self.iterative_scheme = iterative

        self.logger = logger or CustomLogger.get_logger(__name__)

        self.logger.info(f"Starting Chord node {repr(self)} id: {self.id}")

        self.folder = Path(f"storage/{str(self.id)}")
        self.folder.mkdir(parents=True, exist_ok=True)
        os.chdir(self.folder)
        folder = Path.cwd()

        cryptoname = 'cert'
        keypair_path = folder / f"{cryptoname}.crt", folder / f"{cryptoname}.key"
        ca_path = folder / f"ca.crt"

        if keypair is not None and len(keypair) == 2:
            keypair_path[0].write_text(keypair[0])
            keypair_path[1].write_text(keypair[1])

        if ca_file is not None:
            ca_path.write_text(ca_file)

        if keypair_path[0].exists() and keypair_path[1].exists() and ca_path.exists():
            self._rpc_server = ThreadedXRPCServer(addr=self.Address, keypair=keypair_path, ca_file=ca_path,
                                                  allow_none=True,
                                                  logRequests=False)
        else:
            self._rpc_server = ThreadedXRPCServer(addr=self.Address, allow_none=True, logRequests=False)

        # rpc config

        # type(self) to allow inheriting from ChordNode
        required_types = [type(self), RemoteChordNode, InfoContainer]
        self._rpc_server.register_instance(self)
        aditional_types = required_types if not isinstance(aditional_types, list) else aditional_types + required_types
        for t in aditional_types:
            register_type_unmarshaller(t)

        # self._rpc_server.register_introspection_functions()

        # create DHT method
        self.predecessor = None
        self.finger = [None] * (len(IdComparable.hasher_fun("")) * 8)  # m value
        # self.finger[0] = self # better with the getters
        self.r_successors = [None] * (math.ceil(math.log2(len(self.finger))))

        self.database: OrderedUniqueList = OrderedUniqueList()

        self.r_successors_polling = 0.5
        self.r_successors_thread = None
        self.r_successors_d()

        self.fix_fingers_polling = 0.1
        self.fix_fingers_thread = None
        self.fix_fingers_d()

        self.stabilize_polling = 0.5
        self.stabilize_thread = None
        self.stabilize_d()

        self.chk_pred_polling = 0.5
        self.chk_pred_thread = None
        self.chk_pred_d()

        self.fix_content_polling = 0.2
        self.fix_content_thread = None
        self.fix_content_d()

        self.rpc_server_thread = threading.Thread(name="Server", target=self._rpc_server.serve_forever)
        self.rpc_server_thread.start()

        self.debug_thread = threading.Thread(name="DEBUG", target=debug_d, args=(self,), daemon=True)
        self.debug_thread.start()

    def __repr__(self):
        return f"ChordNode {self.Address}"  # + f" {self.id}"

    def _listMethods(self):
        return []  # empty  # list(filter(lambda m: m.__name__.isupper(), list_public_methods(self)))

    def shutdown(self):
        try:
            self._rpc_server.server_close()
        except:
            pass

    # ---------------------- DAEMONS ---------------------- #

    def r_successors_d(self):

        if self.r_successors_thread is None or not self.r_successors_thread.is_alive():
            self.logger.info("Starting R_successors_d")
            self.r_successors_thread = threading.Thread(name="RS", target=self.r_successors_d, daemon=True)
            self.r_successors_thread.start()
            return

        while True:
            successor = self
            for i in range(len(self.r_successors)):
                time.sleep(self.r_successors_polling)
                try:
                    successor = successor.Successor()
                except Exception as e:
                    self.logger.error(f"Succesor down {e}")
                    for j in range(i, len(self.r_successors)):  # will give second opportunity
                        try:
                            s: ChordNode = self.r_successors[j]
                            if s is None:
                                break
                            content = str(time.time_ns())
                            self.logger.debug(f"Ping {content} to {s}")
                            s.Ping(content)
                            if i == 1:  # if down in iteration 1 is that succesor is down, have to fix it
                                self.finger[0] = s
                                self.r_successors.pop(j)
                                self.r_successors.append(None)
                                break
                        except Exception as e2:
                            self.logger.error(f"Err2 {e}")
                            self.r_successors.pop(j)
                            self.r_successors.append(None)

                if successor == self or successor in self.r_successors[:i]:
                    self.r_successors[i:] = [None] * (len(self.r_successors) - i)
                    break
                self.r_successors[i] = successor

    def stabilize_d(self):
        """
        called periodically, verifies n’s immediate successor, and tells the successor about n.
        """
        if self.stabilize_thread is None or not self.stabilize_thread.is_alive():
            self.logger.info("Starting stabilize_d")
            self.stabilize_thread = threading.Thread(name="ST", target=self.stabilize_d, daemon=True)
            self.stabilize_thread.start()
            return

        while True:
            successor = self.Successor()
            try:
                x = successor.Predecessor()
                if between(L=self.id, R=successor.id, id_=x.id) or (successor == self and x != self):
                    self.logger.warning(f"StabSucc from {successor} to {x}")
                    self.finger[0] = x
                    successor = x
            except BaseException as e:  # maybe catch spec exept
                self.logger.error(f"Err stabilizing {e}")

            try:
                if successor != self:
                    successor.Notify(self.Address[1])  # notify my port
            except BaseException as e:
                self.logger.error(f"Err notifiying {e}")
            time.sleep(self.stabilize_polling)

    def chk_pred_d(self):
        '''
         called periodically. checks whether predecessor has failed
        '''
        if self.chk_pred_thread is None or not self.chk_pred_thread.is_alive():
            self.logger.info("Starting chk_pred_d")
            self.chk_pred_thread = threading.Thread(name="CP", target=self.chk_pred_d, daemon=True)
            self.chk_pred_thread.start()
            return

        while True:
            pred: "ChordNode" = self.predecessor
            try:
                if pred is not None:
                    content = str(time.time_ns())
                    self.logger.debug(f"Ping {content} to {pred}")
                    pred.Ping(content)
            except BaseException as e:
                # now im responsible for the data im backed up so lets send it to my successor
                self.logger.error(f"Cleaning predecessor")
                self.predecessor = None

            time.sleep(self.chk_pred_polling)

    def fix_fingers_d(self):
        """
        called periodically. refreshes finger table entries.
        """
        if self.fix_fingers_thread is None or not self.fix_fingers_thread.is_alive():
            self.logger.info("Starting fix_fingers_d")
            self.fix_fingers_thread = threading.Thread(name="FF", target=self.fix_fingers_d, daemon=True)
            self.fix_fingers_thread.start()
            return

        while True:
            for next_ in range(0, len(self.finger)):
                time.sleep(self.fix_fingers_polling)  # here to avoid hard looping
                fid = (self.id + 2 ** next_) % (2 ** len(self.finger))
                next_succ = self.Find_Successor(fid)
                if next_succ.id == self.id:  # break because i will no longer find something better than me
                    if next_ > 0:
                        self.finger[next_] = None  # clean it
                    break
                if next_succ not in self.finger:
                    self.logger.warning(f"Fixed finger {next_} from {self.finger[next_]} to {next_succ}")
                    self.finger[next_] = next_succ

    def fix_content_d(self):
        """
        called periodically. refreshes info around the ring
        """
        if self.fix_content_thread is None or not self.fix_content_thread.is_alive():
            self.logger.info("Starting fix_content_d")
            self.fix_content_thread = threading.Thread(name="FC", target=self.fix_content_d, daemon=True)
            self.fix_content_thread.start()
            return

        def _propose_and_send(node, info_, recurse):
            try:
                res = node.Owner_Of(info_.id, self.Address[1], True)
            except BaseException as e:
                self.logger.error(f"Err proposing to {node} err: {e}")
                return False
            match res:
                case "y":
                    self.logger.info(f"{node} has {info_.id}")
                case "n":
                    self.logger.warning(f"{node} rejected {info_.id}")
                case "m":
                    self.logger.warning(f"{node} missing {info_.id}")
                    try:
                        node.Push(info_, self.Address[1], recurse, False)
                    except BaseException as e:
                        self.logger.error(f"Err sending {info.id} to {node} in prop {e}")
                        return "n"
                case "-":
                    self.logger.warning(f"{node} is in invalid state")
            return res

        while True:
            polling_interval = max(self.fix_content_polling, 5 / (len(self.database) + 1))
            time.sleep(polling_interval)
            content = self.database
            for info in content:
                time.sleep(polling_interval)
                predecessor = self.Predecessor()
                successor = self.Successor()
                if predecessor == self or successor == self:
                    continue

                im_owner = self.Owner_Of(info.id, self.Address[1], False, self.Address)
                tnode = self if im_owner == "y" else self.Find_Successor(info.id)
                if tnode == self:
                    resp = _propose_and_send(node=successor, info_=info, recurse=False)
                    tnode = successor
                else:
                    recurse_push = False # if tnode == predecessor else True
                    resp = _propose_and_send(node=tnode, info_=info, recurse=recurse_push)

                # not mine and not deleting predecessor keys
                if im_owner == "n" and (resp == "y" or resp == "m") and tnode != predecessor:
                    recurse_del = False  # True if tnode != successor else False
                    self.Delete(info.id, self.Address[1], recurse_del, False, self.Address)

    # ---------------------- DHT CORE OPS ---------------------- #

    def Successor(self) -> "ChordNode":
        return self.finger[0] or self

    def Predecessor(self) -> "ChordNode":
        return self.predecessor or self

    def JOIN(self, dstip, dstport):
        """
        joins to Chord ring containing node n0.
        """
        dst_adr = (dstip, dstport)
        n0 = RemoteChordNode.make_remote_node(dst_adr)
        if n0 == self:
            self.logger.warning("Can't join to self")
            return
        self.logger.info(f"Joining {self.Address} to " + str(dst_adr))
        self.predecessor = None
        try:
            successor = n0.Find_Successor(self.id)
        except Exception as e:
            successor = n0
            self.logger.error(f"Err {e} finding successor setting {n0} on JOIN ")
        if successor == self:
            self.logger.critical("Why returned self? collision?")
        self.finger[0] = successor
        self.logger.info(f"Set successor as {successor}")

    def Find_Successor(self, id_, i_remote=None) -> "ChordNode":

        def _closest_preceding_node(search_id):
            for i in range(len(self.finger) - 1, -1, -1):
                current_finger = self.finger[i]
                if current_finger is not None and between(L=self.id, R=search_id, id_=current_finger.id):
                    return i, current_finger
            return len(self.finger) * 2, self

        id_ = int(id_)
        successor = self.Successor()

        if self.id < id_ <= successor.id:  # ChordNode.between(L=self.id, R=successor.id, id_=id_):
            return successor
        # paper else

        if id_ >= self.id > successor.id:  # im the largest so i will keep em
            return self

        i = len(self.finger) * 2
        while True:
            try:
                i, n0 = _closest_preceding_node(id_)

                if n0 == self:  # avoid loop, paper does not cover this
                    return self.Successor()

                if self.iterative_scheme and i_remote:  # and is a remote call:
                    n0.Ping(str(time.time_ns()))
                    return RedirectNodeResponse(n0)

                successor = n0.Find_Successor(id_)
                return successor
            except Exception as e:
                self.logger.error(f"Find_successor fail: {e}")
                self.finger[i] = None

    def Ping(self, content, dstport=None, inj_addr=None):
        self.logger.debug("Pong " + content)

    def Notify(self, dstport, i_addr=None):
        """
        inj_addr,dstport thinks it might be our predecessor
        """
        addr = i_addr[0], dstport
        n0 = RemoteChordNode.make_remote_node(addr)
        pred = self.predecessor
        if pred is None or between(L=pred.id, R=self.id, id_=n0.id):
            self.logger.warning(f"Notified Updpred from {pred} to {n0}")
            self.predecessor = n0

    # ---------------------- CRUD ---------------------- #

    def Owner_Of(self, id_, dstport, recurse=True, i_addr=None):
        predecessor = self.Predecessor()
        successor = self.Successor()
        n0 = RemoteChordNode.make_remote_node(address=(i_addr[0], dstport))
        if predecessor == self or successor == self:  # todo give me a copy and dont delete it
            self.logger.error(f"Telling {n0} im broke {self.Address}")
            return "-"


        belongs_to_my_range = self.id == id_ or predecessor.id < id_ < self.id  # between(L=predecessor.id, R=self.id, id_=id_)
        im_last_n_key_bigger_than_me = self.id > successor.id and id_ >= self.id
        # in case of remote call # or recurse and predecessor.Owner_of(id_, self.Address[1], False)
        is_from_predecessor_and_valid = predecessor.id == n0.id and (
                predecessor.id > self.id or id_ <= predecessor.id < self.id)

        if im_last_n_key_bigger_than_me or belongs_to_my_range or is_from_predecessor_and_valid:
            res = "y" if id_ in self.database else "m"
            self.logger.info(f"Telling {n0} that {id_} {res} is mine {self.Address} ")
            return res
        else:
            self.logger.log(logging.WARNING if n0 != self else logging.INFO,
                            f"Telling {n0} that {id_} not mine {self.Address}")
            return "n"

    def Push(self, info, dstport, recurse=True, resolve=True, i_addr=None, i_remote=None):
        if resolve and self.Owner_Of(info.id, dstport, True, i_addr) == "n":
            tnode: ChordNode = self.Find_Successor(info.id)
            if tnode != self:
                if self.iterative_scheme and i_remote:
                    return RedirectNodeResponse(tnode)
                return tnode.Push(info, dstport, recurse, True)
        self.database.append(info)
        info.write()
        self.logger.warning(f"{i_addr[0], dstport} Pushed in me {self} this {info} recurse {recurse}")
        if recurse > 0:
            successor = self.Successor()
            if successor != self:
                return successor.Push(info, self.Address[1], False, False)
        return True

    def Delete(self, id_, dstport, recurse=True, resolve=True, i_addr=None, i_remote=None):
        if id_ in self.database:
            self.database.find_like(id_).delete()
            self.database.remove(id_)
            self.logger.warning(f"{i_addr[0], dstport} Deleted in me {self.Address} this {id_} recurse {recurse}")

        if resolve and self.Owner_Of(id_, dstport, True, i_addr) == "n":
            tnode: ChordNode = self.Find_Successor(id_)
            if tnode != self:
                if self.iterative_scheme and i_remote:
                    return RedirectNodeResponse(tnode)
                return tnode.Delete(id_, dstport, recurse, True)

        if recurse > 0:
            successor = self.Successor()
            if successor != self:
                return successor.Delete(id_, self.Address[1], False, False)
        return True

    def Pull(self, id_, dstport, resolve=True, i_addr=None, i_remote=None):  # todo add None to dstport
        value = self.database.find_like(id_)
        if resolve and value is None:
            tnode: ChordNode = self.Find_Successor(id_)
            if tnode != self:
                if self.iterative_scheme and i_remote:
                    return RedirectNodeResponse(tnode)
                return tnode.Pull(id_, dstport, True)
        self.logger.warning(f"{i_addr[0], dstport} Pullede in me {self.Address} this {id_}")
        return value
