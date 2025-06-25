"""
Router using all-pairs Dijkstra algorithm (CPU)
Optimized parallel implementation for best performance
"""

import json
import time
import numpy as np
from collections import defaultdict
from itertools import combinations
import concurrent.futures
import os

# Import Dijkstra implementation
from dijkstra import dijkstra_cpu_parallel

# Detect if Mininet is available
try:
    import mininet
    from onos_api import OnosApi
    MININET_AVAILABLE = True
except ImportError:
    from onos_api_mock import OnosApiMock as OnosApi
    MININET_AVAILABLE = False

# Router configuration constants
DEFAULT_PRIORITY = 10
HOST_SWITCH_WEIGHT = 0.1
MAX_WORKERS = 16
BATCH_SIZE = 1000

def process_batch_worker_dijkstra(host_pairs_batch, distance_matrix, node_to_index, index_to_node, 
                                 port_map, host_lookup, switches_set, adjacency_matrix):
    """Process a batch of host pairs for parallel route computation using Dijkstra results"""
    
    def reconstruct_path_worker(source_node, target_node, distance_matrix, adjacency_matrix, 
                               node_to_index, index_to_node):
        """Reconstruct path using distance matrix and adjacency matrix"""
        if source_node not in node_to_index or target_node not in node_to_index:
            return None
        
        source_idx = node_to_index[source_node]
        target_idx = node_to_index[target_node]
        
        INFNTY = 1e9
        if distance_matrix[source_idx, target_idx] >= INFNTY:
            return None
        
        if source_idx == target_idx:
            return [source_node]
        
        # Reconstruct path using backtracking
        V = len(index_to_node)
        path = [target_idx]
        current = target_idx
        
        while current != source_idx:
            min_dist = INFNTY
            predecessor = -1
            
            # Find predecessor (neighbor with minimum distance + edge weight = current distance)
            for neighbor in range(V):
                if (adjacency_matrix[neighbor, current] > 0 and 
                    abs(distance_matrix[source_idx, neighbor] + adjacency_matrix[neighbor, current] - 
                        distance_matrix[source_idx, current]) < 1e-6):
                    if distance_matrix[source_idx, neighbor] < min_dist:
                        min_dist = distance_matrix[source_idx, neighbor]
                        predecessor = neighbor
            
            if predecessor == -1:
                # Cannot reconstruct - return None
                return None
            
            path.append(predecessor)
            current = predecessor
        
        # Convert indices to node names and reverse
        path.reverse()
        return [index_to_node[idx] for idx in path]
    
    all_flows = set()
    
    for source_mac, target_mac in host_pairs_batch:
        source_ip = host_lookup.get(source_mac)
        target_ip = host_lookup.get(target_mac)
        
        if source_ip == target_ip:
            continue
        
        path = reconstruct_path_worker(source_mac, target_mac, distance_matrix, 
                                     adjacency_matrix, node_to_index, index_to_node)
        
        if not path or len(path) < 3:  # Need at least source-switch-target
            continue
        
        # Generate flows for both directions
        for direction_path in [path, list(reversed(path))]:
            dst_mac = target_mac if direction_path == path else source_mac
            src_mac = source_mac if direction_path == path else target_mac
            
            for i in range(1, len(direction_path) - 1):
                current_switch = direction_path[i]
                if current_switch in switches_set:
                    prev_node = direction_path[i-1]
                    next_node = direction_path[i+1]
                    
                    in_port = port_map.get((current_switch, prev_node))
                    out_port = port_map.get((current_switch, next_node))
                    
                    if in_port and out_port:
                        all_flows.add((
                            current_switch, in_port, out_port, 
                            DEFAULT_PRIORITY, dst_mac, src_mac
                        ))
    
    return list(all_flows)

class RouterDijkstra():
    """Manages routing and flow installation using parallel all-pairs Dijkstra algorithm"""
    
    def __init__(self, topo_file=None, onos_ip='127.0.0.1', port=8181):
        if MININET_AVAILABLE:
            self.api = OnosApi(onos_ip, port)
        else:
            self.api = OnosApi(topo_file=topo_file)
        
        self.hosts = []
        self.switches = []
        self.links = []
        self.topo_file = topo_file
        self.topology_data = self.load_topology_data()
        
        self.mac_to_ip = {}
        self.mac_to_location = {}
        self.port_map = {}
        self.switches_set = set()
        
        # Node mapping for adjacency matrix
        self.node_to_index = {}
        self.index_to_node = {}

    def load_topology_data(self):
        """Load topology data from JSON file with automatic fallback"""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        possible_files = []

        if self.topo_file:
            possible_files.append(self.topo_file)
        else:
            possible_files.append('topology_data_mock.json')
            possible_files.append('topology_data.json')
        
        for filename in possible_files:
            json_path = os.path.join(base_dir, filename)
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    return data
                except Exception as e:
                    print(f"Error loading {filename}: {e}")
                    continue
        
        print("RouterDijkstra: No topology data file found")
        return None

    def clean_dpid(self, dpid):
        """Remove 'of:' prefix from DPID if present"""
        return dpid[3:] if dpid.startswith('of:') else dpid

    def find_distance(self, node1, node2):
        """Search for distance between two nodes in topology JSON"""
        if node1 == node2:
            return 0.0
            
        if not self.topology_data or 'distances' not in self.topology_data:
            return None
        
        distances = self.topology_data['distances']
        possible_keys = [f"{node1}-{node2}", f"{node2}-{node1}"]
        
        for key in possible_keys:
            if key in distances:
                return distances[key]
        
        return None

    def build_lookups(self):
        """Build dictionaries for O(1) lookups"""
        self.mac_to_ip.clear()
        self.mac_to_location.clear()
        self.port_map.clear()
        self.switches_set.clear()
        
        # MAC to IP mapping
        for host in self.hosts:
            mac = host['mac']
            ip = host['ipAddresses'][0]
            self.mac_to_ip[mac] = ip
            
            # MAC to location (switch, port)
            location = host['locations'][0]
            switch_id = location['elementId']
            port = location['port']
            self.mac_to_location[mac] = (switch_id, port)

        # Port mapping for links
        for link in self.links:
            src = link['src']['device']
            dst = link['dst']['device']
            src_port = link['src']['port']
            self.port_map[(src, dst)] = src_port

        # Port mapping for hosts
        for host in self.hosts:
            host_mac = host['mac']
            location = host['locations'][0]
            switch_id = location['elementId']
            port = location['port']
            self.port_map[(switch_id, host_mac)] = port

        # Set of switches
        for switch in self.switches:
            self.switches_set.add(switch)

    def validate_hosts_connectivity(self):
        """Validate that all hosts are connected to a switch"""
        disconnected_hosts = []
        
        for host in self.hosts:
            if not host.get('locations') or len(host['locations']) == 0:
                disconnected_hosts.append(host['mac'])
                continue
                
            switch_id = host['locations'][0]['elementId']
            if switch_id not in self.switches_set:
                disconnected_hosts.append(host['mac'])
        
        if disconnected_hosts:
            print(f"Disconnected hosts found: {disconnected_hosts}")
            return False
        
        return True

    def build_adjacency_matrix(self):
        """Build adjacency matrix from topology for Dijkstra algorithm"""
        if not self.topology_data:
            print("Warning: No topology data available, trying to reload...")
            self.topology_data = self.load_topology_data()
            if not self.topology_data:
                raise ValueError("Topology data required for Dijkstra - ensure network is created first")
        
        if not self.hosts:
            raise ValueError("No hosts found in ONOS - ensure network is created and router.update() is called")
        
        # Collect all unique nodes
        nodes = set()
        for host in self.hosts:
            nodes.add(host['mac'])
            switch_id = host['locations'][0]['elementId']
            nodes.add(switch_id)
        
        for link in self.links:
            nodes.add(link['src']['device'])
            nodes.add(link['dst']['device'])
        
        nodes = sorted(list(nodes))
        V = len(nodes)
        
        # Create node mappings
        self.node_to_index = {node: i for i, node in enumerate(nodes)}
        self.index_to_node = {i: node for i, node in enumerate(nodes)}
        
        # Initialize adjacency matrix with float32
        adjacency_matrix = np.zeros((V, V), dtype=np.float32)
        
        # Add host-switch connections
        for host in self.hosts:
            host_mac = host['mac']
            switch_id = host['locations'][0]['elementId']
            i = self.node_to_index[host_mac]
            j = self.node_to_index[switch_id]
            
            weight = HOST_SWITCH_WEIGHT
            adjacency_matrix[i, j] = weight
            adjacency_matrix[j, i] = weight
        
        # Add switch-switch connections
        for link in self.links:
            src = link['src']['device']
            dst = link['dst']['device']
            i = self.node_to_index[src]
            j = self.node_to_index[dst]
            
            clean_src = self.clean_dpid(src)
            clean_dst = self.clean_dpid(dst)
            
            distance = self.find_distance(clean_src, clean_dst)
            weight = float(distance) if distance is not None else 10.0
            
            adjacency_matrix[i, j] = weight
            adjacency_matrix[j, i] = weight
        
        return adjacency_matrix

    def update(self):
        """Update network topology from ONOS"""
        try:
            self.hosts = self.api.get_hosts()
            self.switches = self.api.get_switches()
            self.links = self.api.get_links()
            
            self.build_lookups()
            self.validate_hosts_connectivity()
            
        except Exception as e:
            print(f"Error updating topology: {e}")
            self.hosts = []
            self.switches = []
            self.links = []

    def generate_flows(self, flow_tuples):
        """Generate flow structures from tuples"""
        return [
            {
                'switch_id': switch,
                'output_port': out_port,
                'priority': priority,
                'isPermanent': True,
                'eth_dst': dst,
                'eth_src': src,
                'in_port': in_port
            }
            for switch, in_port, out_port, priority, dst, src in flow_tuples
        ]

    def push_flows_to_onos(self, flows_data, batch_size=5000):
        """Send flows to ONOS in sequential batches"""
        batches = [flows_data[i:i + batch_size] for i in range(0, len(flows_data), batch_size)]
        
        all_results = []
        for batch in batches:
            batch_result = self.api.push_flows_batch(batch)
            all_results.extend(batch_result)
        
        return all_results

    def install_all_routes(self, parallel=True):
        """
        Install all routes using parallel all-pairs Dijkstra algorithm (default method)
        
        Args:
            parallel (bool): Ignored - parallel processing is always used for optimal performance
        """
        print("Installing routes using parallel Dijkstra processing...")
        
        # Build adjacency matrix
        adjacency_matrix = self.build_adjacency_matrix()
        V = len(self.index_to_node)
        
        # Execute all-pairs Dijkstra (always parallel for best performance)
        dijkstra_start = time.time()
        distance_matrix = dijkstra_cpu_parallel(V, adjacency_matrix, max_workers=MAX_WORKERS)
        dijkstra_time = time.time() - dijkstra_start
        
        # Get unique hosts
        unique_hosts = {host['ipAddresses'][0]: host for host in self.hosts}
        host_macs = [host['mac'] for host in unique_hosts.values()]
        
        if len(host_macs) < 2:
            return []

        # Create host pairs
        host_pairs = list(combinations(host_macs, 2))
        unique_flows_final = set()

        # Parallel processing with ProcessPoolExecutor
        batch_size = max(BATCH_SIZE, len(host_pairs) // (MAX_WORKERS * 2))
        host_batches = [host_pairs[i:i + batch_size] for i in range(0, len(host_pairs), batch_size)]

        with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [
                executor.submit(
                    process_batch_worker_dijkstra,
                    batch,
                    distance_matrix,
                    self.node_to_index,
                    self.index_to_node,
                    self.port_map,
                    self.mac_to_ip,
                    self.switches_set,
                    adjacency_matrix
                )
                for batch in host_batches
            ]
            
            # Collect results
            for future in concurrent.futures.as_completed(futures):
                try:
                    flow_list = future.result()
                    unique_flows_final.update(flow_list)
                except Exception as e:
                    print(f"Process batch failed: {e}")

        # Generate and push flows
        all_flows = self.generate_flows(list(unique_flows_final))

        if all_flows:
            api_start = time.time()
            api_results = self.push_flows_to_onos(all_flows)
            api_time = time.time() - api_start
            print(f"Parallel Dijkstra processing: {len(all_flows)} flows installed")
        
        return all_flows