import argparse
from pathlib import Path

import logging
import os

parser = argparse.ArgumentParser(description='Bootstrap a testnet')
parser.add_argument('--baseport', type=int, default=4440, help='Base port')
parser.add_argument('--bootstrap_node_count', type=int, default=3, help='Number of bootstrap nodes')
parser.add_argument('--stepsize', type=int, default=1, help='Stepsize for bootstrap nodes')
parser.add_argument("--joinport", type=int, default=4440, help="Port of the node to join")
args = parser.parse_args()

logger = logging.getLogger(__name__)
logger.setLevel(level=logging.DEBUG)

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

joinport = args.joinport or args.baseport
logger.info("Booting node " + str(args.baseport))
for i in range(args.baseport, args.baseport + args.bootstrap_node_count):
    os.system(basecommand + " " + str(path) + " --baseport " + str(i) + " --joinport " + str(joinport))
    logger.info("Booting node " + str(i) + " and joining to " + str(joinport))
    if not args.joinport:
        joinport = i

# input("Press Enter to continue...")
