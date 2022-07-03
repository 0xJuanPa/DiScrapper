import math
import os

import sys
import threading
import time
import streamlit as st
import graphviz as graphviz
from multiprocessing.connection import Listener
from streamlit.scriptrunner.script_run_context import add_script_run_ctx

from streamlit import cli as stcli

DEBUG = True if 'DEBUG' in os.environ else False

if not st._is_running_with_streamlit:
    # parser = argparse.ArgumentParser(description='Testnet viewer')
    # parser.add_argument('--dbgport', type=int, default=6000, help='Debug port')
    # parser.add_argument('--stport', type=int, default=6000, help='Streamlit port')
    # args = parser.parse_args()

    print("Booting up...")
    sys.argv = ["streamlit", "run", __file__]
    stcli.main()
    # sys.exit(stcli.main())


class Visiblenode:
    def __init__(self, value):
        node, self.pred, self.succ, self.finger, self.rsucc, self.database = value
        self.id = node.id
        self.addr = node.addr
        self.rlen = len(self.rsucc)
        self.rsucc = list(filter(lambda t: t[1] is not None, enumerate(self.rsucc)))
        self.finger = list(filter(lambda t: t[1] is not None, enumerate(self.finger)))

        # get current time
        self.lastknown = time.time()

    def __repr__(self):
        return f"({':'.join(map(str, self.addr))})"


if "init" not in st.session_state:
    st.session_state.init = True
    st.session_state.layout = 'circo'
    st.session_state.splines = 'curved'


def toggle_layout():
    if st.session_state.layout == 'circo':
        st.session_state.layout = "neato"
    else:
        st.session_state.layout = 'circo'


def toggle_splines():
    if st.session_state.splines == 'curved':
        st.session_state.splines = "true"
    else:
        st.session_state.splines = 'curved'


known_nodes = dict()
listening = []


# just to explore this way instead session state
@st.cache(hash_funcs={tuple: id})
def get_storage():
    return listening, known_nodes


def config_and_listen():
    listening, known_nodes = get_storage()
    if len(listening) > 0:
        return
    listening.append(True)
    print('starting listener')
    listener = Listener(("127.0.0.1", 6000))
    while True:
        try:
            conn = listener.accept()
            value = conn.recv()
            vn = Visiblenode(value)
            known_nodes[vn.id] = vn
        except Exception as e:
            print("error", e)


def changed_vnodes(old, new):
    if len(old) != len(new):
        return True
    for o, n in zip(old, new):
        if o.id != n.id:
            return True
        if len(o.database) != len(n.database):
            return True
        if len(o.finger) != len(n.finger):
            return True
        if len(o.rsucc) != len(n.rsucc):
            return True
        if o.succ.id != n.succ.id:
            return True
        if o.pred.id != n.pred.id:
            return True
        for of, nf in zip(o.finger, n.finger):
            if of[1].id != nf[1].id:
                return True
        for os, ns in zip(o.rsucc, n.rsucc):
            if os[1].id != ns[1].id:
                return True
    return False


def calculate(old, force=False):
    lastsecs = time.time()
    listening, known_nodes = get_storage()
    val = list(filter(lambda n: n.lastknown < lastsecs - 5, known_nodes.values()))
    for node in val:
        print("removing", node)
        del known_nodes[node.id]

    vnodes = list(sorted(known_nodes.values(), key=lambda n: n.id))

    if old is not None and not force and not changed_vnodes(old, vnodes):
        return None, None

    graph = graphviz.Digraph()
    # set layout
    graph.attr(rankdir="RL")
    graph.graph_attr['layout'] = st.session_state.layout
    graph.graph_attr['overlap'] = 'false'
    graph.graph_attr['splines'] = st.session_state.splines
    graph.node_attr['shape'] = 'circle'
    graph.node_attr['fixedsize'] = 'true'
    # print(f"made graph wit spline:{st.session_state.splines} and layout:{st.session_state.layout}")

    known = set(map(lambda n: n.id, vnodes))
    added_edges = set()
    if len(vnodes) > 0:
        # use kosaraju to detect max connected components and relayoaut each of them

        rvnodes = list(reversed(vnodes))
        radius = len(rvnodes) / 4 + 1
        rot = (math.pi / 2 + math.pi / len(rvnodes) + (math.pi / len(rvnodes)))
        for i in range(0, len(rvnodes)):
            x = math.cos((math.pi * 2 * (i / len(rvnodes))) + rot) * radius
            y = math.sin((math.pi * 2 * (i / len(rvnodes))) + rot) * radius
            shape = "doublecircle" if i == len(rvnodes) - 1 else "circle"
            n = str(rvnodes[i].addr)
            graph.node(n, pos=f"{x},{y}!", shape=shape, width=str(len(n) / 15))

        for node in vnodes:
            nodestr = str(node.addr)
            succstr = str(node.succ.addr)
            if nodestr != succstr:
                if node.succ.id in known:
                    graph.edge(nodestr, succstr, color='black', penwidth="2")
                    added_edges.add((nodestr, succstr))

            predstr = str(node.pred.addr)
            if nodestr != predstr:
                if node.pred.id in known:
                    graph.edge(nodestr, predstr, color='red')

        for node in vnodes:
            nodestr = str(node.addr)
            for i, fing in node.finger:
                fingstr = str(fing.addr)
                if (nodestr, fingstr) not in added_edges:
                    if fing.id in known:
                        graph.edge(nodestr, fingstr, label=f"{i}", color='blue')
                        # added_edges.add((nodestr, fingstr))

        for node in vnodes:
            nodestr = str(node.addr)
            for i, rs in node.rsucc:
                rsstr = str(rs.addr)
                if (nodestr, rsstr) not in added_edges:
                    if rs.id in known:
                        graph.edge(nodestr, rsstr, label=f"{i}", color='green')
                        # added_edges.add((nodestr, rsstr))

    return graph, vnodes


def render():
    placeholder = st.container()
    graphplace = placeholder.empty()
    infoplace = placeholder.empty()
    prev_vnodes = None
    prev_layout = st.session_state.get("layout", "") + st.session_state.get("splines", "")
    while True:
        force = False
        if prev_layout != st.session_state.get("layout", "") + st.session_state.get("splines", ""):
            print('changed layout')
            force = True
            prev_layout = st.session_state.get("layout", "") + st.session_state.get("splines", "")
        graph, vnodes = calculate(prev_vnodes, force)
        if graph is not None:
            prev_vnodes = vnodes
            print("pritning graph")
            graph_container = graphplace.container()
            graph_container.markdown('# Graph')
            graph_container.graphviz_chart(graph)
            legendc = graph_container.empty()
            if len(vnodes):
                legend = legendc.container()
                legend.markdown('<span style="color:red">Predecessor</span>', unsafe_allow_html=True)
                legend.markdown('<span style="color:black">Successor</span>', unsafe_allow_html=True)
                legend.markdown('<span style="color:blue">Finger</span>', unsafe_allow_html=True)
                legend.markdown('<span style="color:green">R-Successor</span>', unsafe_allow_html=True)
                legend.button('Relayout ' + st.session_state.layout, key="rl" + str(time.time_ns()),
                              on_click=toggle_layout)
                legend.button('Edges ' + st.session_state.splines, key="ed" + str(time.time_ns()),
                              on_click=toggle_splines)
        if vnodes is not None:
            print("pritning info")
            info_container = infoplace.container()
            info_container.markdown("""---""")
            info_container.markdown(f'# Info of the {len(vnodes)} Nodes')
            info_container.markdown('Nodes ordered by id')
            columns = info_container.empty()
            if len(vnodes):
                columns = columns.container()
                maxcol = 5
                remaining = len(vnodes)
                rows = math.ceil(len(vnodes) / maxcol)
                for i in range(0, rows):
                    stcol = columns.columns(min(maxcol, remaining))
                    remaining -= maxcol
                    for j, c in enumerate(stcol):
                        index = i * maxcol + j
                        n = vnodes[index]
                        c.markdown(f'#### {index + 1}. {n}')
                        c.markdown(f'Pred: \r\n * {n.pred}')
                        c.markdown(f'Succ: \r\n * {n.succ}')
                        r = "\r\n * ".join(map(str, n.rsucc))
                        c.markdown(f'({n.rlen})R-Succ: \r\n * {r}')
                        f = "\r\n * ".join(map(str, n.finger))
                        c.markdown(f'Fingers: \r\n * {f}')
                        c.markdown("""---""")
                        d = "\r\n * ".join(map(str, n.database))
                        c.markdown(f'Database: \r\n * {d}')
                    columns.markdown("""---""")

        time.sleep(1)


st.set_page_config(layout="wide")
listen_thread = threading.Thread(target=config_and_listen, daemon=True)
add_script_run_ctx(listen_thread)
listen_thread.start()

render()
