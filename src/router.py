import networkx as nx # type: ignore
from onos_api import OnosApi
import time

class Router():
    def __init__(self, onos_ip=None, port=None):
        self.hosts = None
        self.switches = None
        self.links = None
        self.api = OnosApi(onos_ip, port)
        self.update()

    def update(self):
        self.hosts = self.api.get_hosts()
        self.switches = self.api.get_switches()
        self.links = self.api.get_links()


    def find_port(self, src, dst):
        """
        Returns the port that connects switch src to device dst

        Args:
            src (str): e.g., "of:0000000000000001"
            dst (str): e.g., "of:0000000000000002" or "00:00:00:00:00:A1"
        """

        # if the link is beetween two switches
        for link in self.links:
            if link['src']['device'] == src and link['dst']['device'] == dst:
                return link['src']['port']
        
        # If the link is beetwween a switch and a host
        for host in self.hosts:
            if host['mac'] == dst and host['locations'][0]['elementId'] == src:
                return host['locations'][0]['port']

        return None


    def build_graph(self):
        G = nx.Graph()

        for switch in self.switches:
            G.add_node(switch)

        # Add host edges
        for host in self.hosts:
            switch = host['locations'][0]['elementId']
            G.add_node(host['mac'])                     # add host node (e.g., MAC)
            G.add_edge(host['mac'], switch)

        for link in self.links:
            G.add_edge(link['src']['device'], link['dst']['device'])

        return G

    def create_flow(self, from_hop, to_hop, final_dst):
        """
        Create a flow that goes from "from_hop" to "to_hop" when trying to reach "final_dst¨

        Args:
            from_hop (str): Switch IDe.g. "of:0000000000000001"
            to_hop (str): Switch ID or MAC ADDR e.g. "of:0000000000000002" or "00:00:00:00:00:A1"
            final_dst (src): MAC ADDR e.g. "00:00:00:00:00:A1"
        """
        port = self.find_port(from_hop, to_hop)
        status, msg = self.api.push_flow(from_hop, final_dst, port)
        print(f"{status} -> {msg} for flow ({from_hop}, {to_hop}, {final_dst})")



    def heuristic(u, v):
    return 0
    
    def install_all_routes(self):
        graph = self.build_graph()
        paths = []

        for src in self.hosts:
            for tgt in self.hosts:
                source = src['mac']
                target = tgt['mac']

                if source == target:
                    continue

                path = nx.astar_path(graph, source=source, target=target)
                paths.append(path) 

        for path in paths:
            final_dst = path[len(path) - 1]
            for i in range(len(path) - 1):
                hop = path[i]
                next_hop = path[i+1]

                if hop not in self.switches:
                    continue

                self.create_flow(from_hop=hop, to_hop=next_hop, final_dst=final_dst)

def main():
    print("Installing routing intents for all host pairs...")
    start = time.time()
    router = Router()
    router.install_all_routes()
    total_time = time.time() - start
    print(f"Time spend to generate routs {total_time}")
    print("Done.")

if __name__ == "__main__":
    main()

