import argparse
import time
from pathlib import Path
from testnet_cert_utils import generate_certificate, generate_ca_certificate, save_certificate
import logging
import os

parser = argparse.ArgumentParser(description='Bootstrap a testnet')
parser.add_argument('--baseport', type=int, default=4440, help='Base port')
parser.add_argument('--bootstrap_node_count', type=int, default=3, help='Number of bootstrap nodes')
parser.add_argument("--secure", type=bool, default=True, help="Use secure communication")
parser.add_argument('--stepsize', type=int, default=1, help='Stepsize for bootstrap nodes')
parser.add_argument("--joinport", type=int, default=None, help="Port of the node to join")

interface = "127.0.0.1"

args = parser.parse_args()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

logger.info("Bootstrapping " + str(args.bootstrap_node_count) + " nodes from " + str(
    args.baseport) + " with stepsize " + str(args.stepsize))
path = Path(__file__).absolute().parents[0] / "DiSboot.py"
basecommand = None
if os.name != "nt":
    # make sure x-terminal-emulator link is set
    terminal = os.popen('which x-terminal-emulator').read().strip()
    if terminal == '':
        terminal = ["gnome-terminal", "konsole", "xterm", "kitty"]
        for term in terminal:
            if os.system("which " + term) == 0:
                terminal = term
                break
    basecommand = terminal + " -e python3"
else:
    basecommand = "start cmd /c py -3.10"

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
        ca, cakey = generate_ca_certificate(f"Discrapper testing CA {time.time()}")
        ca_path, cakey_path = save_certificate("storage/ca", ca, cakey)
else:
    ca_path = ""
    ca = None
    cakey = None

folder = Path.cwd() / Path(f"storage")
folder.mkdir(parents=True, exist_ok=True)

joinport = args.joinport or args.baseport
logger.info("Booting node " + str(args.baseport))
for i in range(args.baseport, args.baseport + args.bootstrap_node_count):
    if args.secure:
        cert, key = generate_certificate(f"{interface}:{i}", ca, cakey)
        cert_path, key_path = save_certificate(f"storage/{interface}-{i}", cert, key=key)
        os.system(
            f"{basecommand} {str(path)} --baseport {str(i)} --joinport {str(joinport)} --ca-path {ca_path} --cert-path {cert_path} --key-path {key_path}")
    else:
        os.system(f"{basecommand} {str(path)} --baseport {str(i)} --joinport {str(joinport)}")
    logger.info("Booting node " + str(i) + " and joining to " + str(joinport))
    if not args.joinport:
        joinport = i

# input("Press Enter to continue...")
