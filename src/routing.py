import networkx as nx # type: ignore
from onos_api import *
import time

hosts = get_hosts()
switches = get_switches()
links = get_links()

def find_port(src, dst):
    """
    Returns the port that connects switch src to device dst

    Args:
        src (str): e.g., "of:0000000000000001"
        dst (str): e.g., "of:0000000000000002" or "00:00:00:00:00:A1"
    """

    # if the link is beetween two switches
    for link in links:
        if link['src']['device'] == src and link['dst']['device'] == dst:
            return link['src']['port']
    
    # If the link is beetwween a switch and a host
    for host in hosts:
        if host['mac'] == dst and host['locations'][0]['elementId'] == src:
            return host['locations'][0]['port']

    return None


def build_graph():
    G = nx.Graph()

    for switch in switches:
        G.add_node(switch)

    # Add host edges
    for host in hosts:
        switch = host['locations'][0]['elementId']
        G.add_node(host['mac'])                     # add host node (e.g., MAC)
        G.add_edge(host['mac'], switch)

    for link in links:
        G.add_edge(link['src']['device'], link['dst']['device'])

    return G

def create_flow(from_hop, to_hop, final_dst):
    """
    Create a flow that goes from "from_hop" to "to_hop" when trying to reach "final_dst¨

    Args:
        from_hop (str): Switch IDe.g. "of:0000000000000001"
        to_hop (str): Switch ID or MAC ADDR e.g. "of:0000000000000002" or "00:00:00:00:00:A1"
        final_dst (src): MAC ADDR e.g. "00:00:00:00:00:A1"
    """
    #print(f"Generating flow from {from_hop} to {to_hop} when trying to reach {final_dst}")
    port = find_port(from_hop, to_hop)
    status, msg = push_flow(from_hop, final_dst, port)
    #print(f"  → {status}: {msg}")
    pass

def install_all_routes():
    graph = build_graph()
    paths = []

    for src in hosts:
        for tgt in hosts:
            source = src['mac']
            target = tgt['mac']

            if source == target:
                continue

            path = nx.shortest_path(graph, source=source, target=target)
            paths.append(path) 

    for path in paths:
        final_dst = path[len(path) - 1]
        for i in range(len(path) - 1):
            hop = path[i]
            next_hop = path[i+1]

            if hop not in switches:
                continue

            create_flow(from_hop=hop, to_hop=next_hop, final_dst=final_dst)

def main():
    print("Installing routing intents for all host pairs...")
    start = time.time()
    install_all_routes()
    total_time = time.time() - start
    print(f"Time spend to generate routs {total_time}")
    print("Done.")

if __name__ == "__main__":
    main()

