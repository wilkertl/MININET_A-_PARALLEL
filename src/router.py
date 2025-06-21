import networkx as nx
from itertools import combinations
import time
import json
import os

from onos_api import OnosApi 

class Router():
    def __init__(self, onos_ip='127.0.0.1', port=8181):
        self.api = OnosApi(onos_ip, port)
        self.hosts = []
        self.switches = []
        self.links = []
        self.topology_data = self.load_topology_data()
        self.update()

    def load_topology_data(self):
        """Loads topology data from JSON file"""
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'topology_data.json')
        
        if not os.path.exists(json_path):
            print("WARNING: topology_data.json file not found.")
            return None
            
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"✓ Data loaded: {len(data.get('distances', {}))} distances, {len(data.get('bandwidth', {}))} links")
        return data

    def find_distance(self, node1, node2):
        """Searches for distance between two nodes in topology JSON"""
        if node1 == node2:
            return 0.0
            
        if not self.topology_data or 'distances' not in self.topology_data:
            raise ValueError(f"Data not available for {node1}-{node2}")
        
        distances = self.topology_data['distances']
        possible_keys = [f"{node1}-{node2}", f"{node2}-{node1}"]
        
        for key in possible_keys:
            if key in distances:
                return distances[key]
        
        raise KeyError(f"Distance not found between {node1} and {node2}")

    def clean_dpid(self, dpid):
        """Removes 'of:' prefix from DPID if present"""
        return dpid[3:] if dpid.startswith('of:') else dpid

    def get_host_ip_from_mac(self, mac):
        """Converts host MAC to IP"""
        for host in self.hosts:
            if host['mac'] == mac:
                return host['ipAddresses'][0]
        return None

    def heuristic_function(self, node1, node2):
        """Heuristic function for A* based on real distance"""
        search_node1 = self.get_host_ip_from_mac(node1) or self.clean_dpid(node1)
        search_node2 = self.get_host_ip_from_mac(node2) or self.clean_dpid(node2)
        return self.find_distance(search_node1, search_node2)

    def get_edge_weight(self, node1, node2):
        """Calculates edge weight based on distance"""
        clean_node1 = self.clean_dpid(node1) if node1.startswith('of:') else node1
        clean_node2 = self.clean_dpid(node2) if node2.startswith('of:') else node2
        return self.find_distance(clean_node1, clean_node2)

    def update(self):
        """Updates network topology from ONOS"""
        self.hosts = self.api.get_hosts()
        self.switches = self.api.get_switches()
        self.links = self.api.get_links()

    def find_port(self, src, dst):
        """Finds connection port between two devices"""
        for link in self.links:
            if link['src']['device'] == src and link['dst']['device'] == dst:
                return link['src']['port']
        for host in self.hosts:
            if host['mac'] == dst and host['locations'][0]['elementId'] == src:
                return host['locations'][0]['port']
        return None
    
    def build_graph(self):
        """Builds topology graph with distance-based weights"""
        if not self.topology_data:
            raise ValueError("Topology data required for A*")
        
        G = nx.Graph()
        
        if not self.hosts:
            raise ValueError("No hosts found in ONOS")
        
        for host in self.hosts:
            host_mac = host['mac']
            host_ip = host['ipAddresses'][0]
            switch_id = host['locations'][0]['elementId']
            clean_switch_id = self.clean_dpid(switch_id)
            weight = self.get_edge_weight(host_ip, clean_switch_id)
            G.add_edge(host_mac, switch_id, weight=weight)
        
        if not self.links:
            raise ValueError("No switch links found")
        
        for link in self.links:
            src = link['src']['device']
            dst = link['dst']['device']
            clean_src = self.clean_dpid(src)
            clean_dst = self.clean_dpid(dst)
            weight = self.get_edge_weight(clean_src, clean_dst)
            G.add_edge(src, dst, weight=weight)
        
        return G

    def install_all_routes(self):
        """Installs routes using A* with heuristic based on real distances"""
        graph = self.build_graph()
        unique_flows_final = set()

        # Filter hosts with unique IPs
        unique_hosts = {}
        for host in self.hosts:
            host_ip = host['ipAddresses'][0]
            if host_ip not in unique_hosts:
                unique_hosts[host_ip] = host
        
        host_macs = [host['mac'] for host in unique_hosts.values()]
        print(f"*** Calculating A* routes for {len(host_macs)} unique hosts...")
        
        for source_mac, target_mac in combinations(host_macs, 2):
            source_ip = self.get_host_ip_from_mac(source_mac)
            target_ip = self.get_host_ip_from_mac(target_mac)
            
            if source_ip == target_ip:
                continue
            
            path = nx.astar_path(
                graph, 
                source=source_mac, 
                target=target_mac,
                heuristic=self.heuristic_function,
                weight='weight'
            )
            
            # Process normal and reverse paths
            for direction_path in [path, list(reversed(path))]:
                dst_mac = target_mac if direction_path == path else source_mac
                src_mac = source_mac if direction_path == path else target_mac
                
                for i in range(1, len(direction_path) - 1): 
                    if direction_path[i] in self.switches:  
                        in_port = self.find_port(direction_path[i], direction_path[i-1])  
                        out_port = self.find_port(direction_path[i], direction_path[i+1])  
                        
                        if in_port and out_port:
                            unique_flows_final.add((
                                direction_path[i], in_port, out_port, 
                                10, dst_mac, src_mac
                            ))

        all_flows_unique = [
            {
                'switch_id': switch,
                'output_port': out_port,
                'priority': priority,
                'isPermanent': True,
                'eth_dst': dst,
                'eth_src': src,
                'in_port': in_port
            }
            for switch, in_port, out_port, priority, dst, src in unique_flows_final
        ]

        if not all_flows_unique:
            raise ValueError("No flows generated")

        start_time = time.time()
        results = self.api.push_flows_batch(all_flows_unique)
        success_count = sum(1 for status, _ in results if status == 201)
        total_time = time.time() - start_time
        
        print(f"A* creation completed: {success_count}/{len(all_flows_unique)} flows in {total_time:.2f}s")