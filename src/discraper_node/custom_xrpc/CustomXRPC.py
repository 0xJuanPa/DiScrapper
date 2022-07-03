import json
from http import client
import inspect
import xmlrpc
import ssl
from urllib import parse as urlparse
from socketserver import ThreadingMixIn
from xmlrpc.client import Transport, Marshaller, Unmarshaller, ServerProxy
from xmlrpc.server import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
from ..custom_logger import get_logger

ServerProxy = ServerProxy  # to avoid removal

logger = get_logger(__name__)

try:
    # optional this will prevent some xml recursive DOS as Bombs and million lauhgs, wich python xml is vulnerable
    import defusedxml.xmlrpc as xml_sec

    xml_sec.monkey_patch()
    logger.info("Patched xmlvulns")
except ImportError:
    logger.warning("DefusedXML not installed, youre vulnerable to XML DOSes ")


class RedirectNodeResponse:
    def __init__(self, node):
        self.Address = getattr(node, "Address", None) or node


class DiSRequestHandler(SimpleXMLRPCRequestHandler):

    def _is_valid_post_method(self, method: str):
        if not method[0].isupper():
            logger.error('method "' + method + f'" is not supported on POST by {self.client_address}')
            return False
        return True

    def _is_valid_get_method(self, method: str):
        if not all(map(str.isupper, method)):
            logger.error('method "' + method + f'" is not supported on GET {self.client_address}')
            return False
        return True

    def _report_403(self):
        # Report a 404 error
        self.send_response(403)
        response = b'Not Authenticated'
        self.send_header("Content-type", "text/plain")
        self.send_header("Content-length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def _report_500(self,e):
        self.send_response(500)
        response = f'Internal Server Error {e}'
        self.send_header("Content-type", "text/plain")
        self.send_header("Content-length", str(len(response)))
        self.end_headers()
        self.wfile.write(response.encode("utf-8"))

    def do_GET(self):
        # clean url + rest
        # self.send_header("Connection", "close")  # this will close the connection here and report client to do same

        url = urlparse.urlsplit(self.path)  # urlsplit, urlparse parses also ?param=val&p=val
        p = url.path.lstrip("/")
        path = p.split("/")
        if len(path) == 0:
            return self.report_404()
        method = path[0]

        if not self._is_valid_get_method(method):
            self.report_404()
            return

        meth = getattr(self.server.instance, method)
        meth_params = inspect.signature(meth).parameters
        param_count = len(meth_params) - (1 if "i_remote" in meth_params else 0) # Self is not counted
        # qs = urlparse.parse_qs(url.query)
        if param_count > 0 and len(path) > 1:
            p = url.path.lstrip("/")
            path = p.split("/",param_count) # +1 because of method
            params = tuple(path[1:])
        else:
            params = tuple()
        logger.debug(f"Clean Rest Called {method} by {self.client_address}")

        try:
            result = self.server._dispatch(method, params)
        except Exception as e:
            self._report_500(e)
            return

        if isinstance(result, RedirectNodeResponse):
            host = f"{result.Address[0]}:{result.Address[1]}"
            # new_url = urlparse.urlparse(self.request)
            # new_url._replace(netloc=host)
            proto = "https://" if  isinstance(self.server.socket,ssl.SSLSocket) else "http://"
            new_url =  proto  + host + self.path
            self.send_response(301)
            self.send_header("Location", new_url)
            self.end_headers()
            return
        self.send_response(200)
        # set content to json
        self.send_header("Content-type", "application/json")
        try:
            encoded_result = json.JSONEncoder().encode(result)
        except Exception as e:
            self._report_500(e)
            return
        self.end_headers()
        self.wfile.write(encoded_result.encode("utf-8"))

    def do_POST(self) -> None:
        # self.send_header("Connection", "close")  # this will close the connection here and report client to do same
        cert = None
        # force clients to authenticate this is incompatible with browsers
        if isinstance(self.connection, ssl.SSLSocket):
            cert = self.connection.getpeercert()
            if cert is None or cert == {}:
                self._report_403()
                logger.error(f"Client {self.client_address} did not used a certificate on POST")
                return
        logger.debug(f"XMLRequest from {self.client_address} and cert {cert}")
        super().do_POST()

    def _dispatch(self, method: str, params: tuple):

        if not self._is_valid_post_method(method):
            return self.report_404()

        logger.debug(f"XMLCalled {method} by {self.client_address}")
        meth = getattr(self.server.instance, method)
        meth_params = inspect.signature(meth).parameters
        if meth_params.get("i_addr", None):
            params = tuple(list(params) + [self.client_address])
        if meth_params.get("i_remote", None):
            params = tuple(list(params) + [True])
        if len(params) > len(meth_params):
            raise Exception("Invalid call to Injected method")
        result = self.server._dispatch(method, params)
        return result


class DiSTransport(Transport):
    def __init__(self, proxy: str = None, ca_file=None, keypair=None, timeout=None, follow_redirects=True,
                 baseport=None):
        super().__init__()
        self.proxy = proxy
        self.baseport = baseport
        self.followRedirects = follow_redirects
        self.timeout = timeout
        if keypair is not None and len(keypair) == 2 and ca_file is not None:
            self.context: ssl.SSLContext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            self.context.minimum_version = ssl.TLSVersion.TLSv1_3
            self.context.maximum_version = ssl.TLSVersion.TLSv1_3
            self.context.check_hostname = False
            self.context.verify_flags = ssl.VerifyFlags.VERIFY_DEFAULT  # no crl check
            # context.verify_flags = ssl.VerifyFlags.VERIFY_CRL_CHECK_CHAIN  # crl check
            self.context.verify_mode = ssl.VerifyMode.CERT_REQUIRED
            self.context.load_cert_chain(certfile=keypair[0], keyfile=keypair[1])
            self.context.load_verify_locations(cafile=ca_file)
        else:
            self.context = None

    # def _range_socket(self, addr):
    #     # mod to return a socket in the range for out connections
    #     host, port = addr.split(":")
    #     for af, socktype, proto, canonname, sa in getaddrinfo(host, port, 0, SOCK_STREAM):
    #         for dstport in range(self.baseport + 1, self.baseport + 10):
    #             try:
    #                 connection = client.HTTPConnection(host=addr, source_address=(sa[0], dstport))
    #                 return connection
    #             except:
    #                 pass
    #     raise Exception("Unable to bind in range")

    def make_connection(self, host):
        # will not use keep alive
        chost, self._extra_headers, x509 = self.get_host_info(host)
        if self.context is not None:
            conn = client.HTTPSConnection(chost, timeout=self.timeout, context=self.context)
        else:
            conn = client.HTTPConnection(chost, timeout=self.timeout)
        return conn

    def request(self, host, handler, request_body, verbose=False):
        while True:
            if self.context is not None:
                pass

            resp = super().request(host, handler, request_body, verbose)
            self.close()  # closing, no keep alive # this mehtod may not do anything though

            if len(resp) != 1 or not (self.followRedirects and isinstance(resp[0], RedirectNodeResponse)):
                break
            resp = resp[0]
            nhost = str(resp.Address[0]) + ":" + str(resp.Address[1])
            logger.info(f"RPC Redirected from {host}  to " + nhost)
            host = nhost
        return resp


class ThreadedXRPCServer(ThreadingMixIn, SimpleXMLRPCServer):
    daemon_threads = True

    def __init__(self, addr, ca_file=None, keypair=None, requestHandler=DiSRequestHandler,
                 logRequests=True, allow_none=False, encoding=None,
                 bind_and_activate=True, use_builtin_types=False):
        SimpleXMLRPCServer.__init__(self, addr, requestHandler, logRequests, allow_none, encoding, bind_and_activate,
                                    use_builtin_types)

        if keypair is not None and len(keypair) == 2 and ca_file is not None:
            self.context: ssl.SSLContext = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            self.context.minimum_version = ssl.TLSVersion.TLSv1_3
            self.context.maximum_version = ssl.TLSVersion.TLSv1_3
            self.context.check_hostname = False
            self.context.verify_flags = ssl.VerifyFlags.VERIFY_DEFAULT  # no crl check
            # context.verify_flags = ssl.VerifyFlags.VERIFY_CRL_CHECK_CHAIN  # crl check
            self.context.verify_mode = ssl.VerifyMode.CERT_OPTIONAL
            self.context.load_verify_locations(cafile=ca_file)
            self.context.load_cert_chain(certfile=keypair[0], keyfile=keypair[1])
            self.socket = self.context.wrap_socket(self.socket)
            logger.info(f"Starting a secure XRPC server on {addr}")
        else:
            logger.info(f"Starting an insecure XRPC server on {addr}")
            self.context = None


# An "encode" method could be defined in each class also
def dump_generic_instance(self: Marshaller, value, write):
    # check for special wrappers
    if hasattr(type(value), "encode"):
        self.write = write
        value.encode(self)
        del self.write
    else:
        # store instance attributes as a struct (really?)
        tag = type(value).__name__
        filtered = dict(filter(lambda x: x[0][0].isupper(),
                               inspect.getmembers(value, lambda x: not inspect.ismethod(x) and not inspect.isclass(x))))
        self.dump_struct({tag: filtered}, write)


class BigInt:
    def __init__(self, value):
        self.Value = str(value)


# to fix int of python
def dump_big_int(self: Marshaller, value, writer):
    try:
        self.dump_long(value, writer)
    except Exception as e:
        self.dispatch["_arbitrary_instance"](self, BigInt(value), writer)


# type(self), maybe restore date & bin ca
xmlrpc.client.Marshaller.dispatch["_arbitrary_instance"] = dump_generic_instance
xmlrpc.client.Marshaller.dispatch[int] = dump_big_int

knw_types = {}


def register_type_unmarshaller(type):
    knw_types[type.__name__] = type  # maybe mov this to classes and search in current module with some sec
    xmlrpc.client.Unmarshaller.dispatch[type.__name__] = my_end_struct


def my_end_struct(self: Unmarshaller, data):
    self.end_struct(data)  # fast look shift reduce or pushdown?
    res = self._stack[-1]
    if isinstance(res, dict) and len(res) == 1:
        if (val := res.get(BigInt.__name__, None)) and isinstance(val, dict):
            res = int(val["Value"])
        elif (val := res.get(RedirectNodeResponse.__name__, None)) and isinstance(val, dict):
            addr = val.get("Address", None)
            res = RedirectNodeResponse(addr)
        elif (k := tuple(res.keys())[0]) and k in knw_types and (val := res.get(k, None)) and isinstance(val, dict):
            res = knw_types[k].unmarshall(val)
    self._stack[-1] = res


xmlrpc.client.Unmarshaller.dispatch["struct"] = my_end_struct
