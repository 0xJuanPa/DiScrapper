import argparse
import time
from pathlib import Path
import logging
import os

parser = argparse.ArgumentParser(description='Bootstrap a testnet')
parser.add_argument('--stepsize', type=int, default=1, help='Stepsize for bootstrap nodes')
parser.add_argument("--interface", type=str, default="127.0.0.1", help="Interface to listen on")
parser.add_argument('--baseport', type=int, default=4440, help='Base port')
parser.add_argument("--joinport", type=int, default=None, help="Port of the node to join")
parser.add_argument('--bootstrap_node_count', type=int, default=3, help='Number of bootstrap nodes')
parser.add_argument("--secure", type=int, default=1, help="Use secure communication 0/1")
parser.add_argument("--dbg", type=str, default=None, help="Debug server string")

args = parser.parse_args()

# comment this out if you want to use the default values
# args.dbg = "127.0.0.1:6000"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

logger.info("Bootstrapping " + str(args.bootstrap_node_count) + " nodes from " + str(
    args.baseport) + " with stepsize " + str(args.stepsize) + f" secure: {args.secure}")
path = Path(__file__).absolute().parents[0] / "DiSboot.py"
basecommand = None
if os.name != "nt":
    # make sure x-terminal-emulator link is set
    terminal = os.popen('which x-terminal-emulator').read().strip()
    found = True
    if terminal == '':
        found = False
        terminal = ["gnome-terminal", "konsole", "xterm"]
        for term in terminal:
            if os.system("which " + term) == 0:
                terminal = term
                found = True
                break
    if found:
        basecommand = terminal + " -e python3"
    else:
        basecommand = "python3 "
else:
    basecommand = "start cmd /c py -3.10"

logger.info("Using basecommand: " + basecommand)

if args.dbg is not None:
    ip, port = args.dbg.split(":")
    if ip == "127.0.0.1":
        logging.info("Starting Debug server: %s", args.dbg)
        port = int(port)
        os.system(f"{basecommand} testnet_visualizer.py --dbg {port}")

if args.secure:
    ca_path = Path("storage/ca.crt")
    cakey_path = Path("storage/ca.key")
    if ca_path.exists() and cakey_path.exists():
        logger.info("CA certificate and key found, using them")
        # pyopenssl load cert and key
        import OpenSSL.crypto
        ca = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, ca_path.open("rb").read())
        cakey = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM, cakey_path.open("r").read())
    else:
        from testnet_cert_utils import generate_certificate, generate_ca_certificate, save_certificate
        logger.info("CA certificate and key not found, generating them")
        ca, cakey = generate_ca_certificate(f"Discrapper testing CA {time.time()}")
        ca_path, cakey_path = save_certificate("storage/ca", ca, cakey)
else:
    ca_path = ""
    ca = None
    cakey = None

folder = Path.cwd() / Path(f"storage")
folder.mkdir(parents=True, exist_ok=True)

joinport = args.joinport or args.baseport
logger.info(f"Booting node {args.interface}:{joinport}")

dbgstr = f"--dbg {args.dbg}" if args.dbg is not None else ""

for i in range(args.baseport, args.baseport + args.bootstrap_node_count):
    if args.secure:
        from testnet_cert_utils import generate_certificate, generate_ca_certificate, save_certificate
        cert, key = generate_certificate(f"{args.interface}:{i}", ca, cakey)
        logger.info(f"Generated certificate for {args.interface}:{i}")
        cert_path, key_path = save_certificate(f"storage/{args.interface}-{i}", cert, key=key)
        os.system(
            f"{basecommand} {str(path)} --interface {args.interface} --baseport {str(i)} --joinaddr {args.interface}:{str(joinport)} {dbgstr} --ca-path {ca_path} --cert-path {cert_path} --key-path {key_path}")
    else:
        os.system(f"{basecommand} {str(path)} --interface {args.interface} --baseport {str(i)} --joinaddr {args.interface}:{str(joinport)} {dbgstr}")
    logger.info(f"Booting node {args.interface}:{i} and joining to {args.interface}:{joinport}")
    if not args.joinport:
        joinport = i

# input("Press Enter to continue...")
