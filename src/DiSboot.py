import argparse
from pathlib import Path

from discraper_node import DiSNode
import pprint

from discraper_node.InfoContainer import InfoContainer
from discraper_node.custom_logger import get_logger
import logging

logger = get_logger(__name__)
logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser(description='Boots a DiSnode')
parser.add_argument("--interface", type=str, default="127.0.0.1", help="Interface to listen on")
parser.add_argument('--baseport', type=int, default=4442, help='Base port')
parser.add_argument("--joinport", type=int, default=4440, help="Port of the node to join")
parser.add_argument("--ca-path", type=str, default=None, help="Path to the CA certificate")
parser.add_argument("--cert-path", type=str, default=None, help="Path to the certificate")
parser.add_argument("--key-path", type=str, default=None, help="Path to the key")

# cd src
#  py -3.10 .\DiSboot.py --baseport 4440 --joinport 4440 --cert-path storage\127.0.0.1-4440.crt --key-path storage\127.0.0.1-4440.key --ca-path storage\ca.crt


args = parser.parse_args()

# # dbg patch
# if args.baseport == 4441:
#     args.ca_path = Path("storage\\ca.crt")
#     args.cert_path = Path("storage\\127.0.0.1-4441.crt")
#     args.key_path = Path("storage\\127.0.0.1-4441.key")

if any(map(lambda e:e is None,[args.ca_path,args.cert_path,args.key_path])) and not all(map(lambda e:e is None,[args.ca_path,args.cert_path,args.key_path])):
    raise Exception("All three of --ca-path, --cert and --key must be specified or none of them")

keypair = None
ca = None

if args.ca_path is not None:
    logger.info("Loading CA certificate from " + args.ca_path)
    logger.info("Loading certificate from " + args.cert_path)
    logger.info("Loading key from " + args.key_path)

    cert = Path(args.cert_path).open("r").read()
    key = Path(args.key_path).open("r").read()
    ca = Path(args.ca_path).open("r").read()
    keypair = (cert, key)
else:
    ca = None
    cert = None
    key = None

node = DiSNode(args.baseport,interface=args.interface, logger=logger, ca_content=ca, keypair_content=keypair)

if args.joinport is not None:
    node.JOIN("127.0.0.1", args.joinport)

while True:
    # menu
    print("j. JOIN")
    print("l. LOGLEVEL")
    print("f. FIND ID")
    print("s. SAVE VALUE")
    print("x. SHUTDOWN")
    print("Empty to print contents")
    choice = input("Enter your choice:\n")
    choice = choice.lower()
    try:
        match choice:
            case "l":
                level = input("Enter log level [10,20,30,40,50]:")
                level = int(level)
                logging.basicConfig(level=level)
            case "j":
                print("\n")
                host = input("Enter the host: ")
                if len(host) < 7:
                    host = "127.0.0.1"
                    print("Invalid host, using localhost")
                try:
                    port = input("Enter the port: ")
                    port = int(port)
                    node.JOIN(host, port)
                except:
                    pass
                print("\n")
            case "x":
                node.shutdown()
                print("\n")
            case "f":
                id_ = input("Enter the id: ")
                try:
                    id_ = int(id_)
                except:
                    print("invalid id must be int")
                cnode = node.Find_Successor(id_)
                print(cnode)
            case "s":
                info = input("Enter the info: ")
                doc = InfoContainer(info)
                res = node.Push(doc, dstport=node.Address[1], recurse=True, resolve=True, i_addr=node.Address)
                logger.info(res)
            case _:
                print(f"{repr(node)}")
                print(f"\nPredecessor: {node.Predecessor()}")
                print(f"\nSuccessor: {node.Successor()}\n")
                print(f"\nFinger table:")
                pprint.pprint(list(filter(lambda t: t[1] is not None, enumerate(node.finger))))
                print(f"\nR succesors:")
                pprint.pprint(list(filter(lambda t: t[1] is not None, enumerate(node.r_successors))))
                print(f"\nDatabase:")
                pprint.pprint(list(filter(lambda t: t[1] is not None, enumerate(node.database))))
                print("\n")

    except Exception as e:
        logger.error(f"Error Main Menu: {e}")
