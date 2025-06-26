"""
Router using PyCUDA parallel Dijkstra implementation
GPU-accelerated routing for large-scale networks
"""

import time
import json
import os
import numpy as np
from itertools import combinations

# Import PyCUDA Dijkstra implementation
from dijkstra import dijkstra_parallel_pycuda, reconstruct_paths_batch_gpu

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

class RouterPyCUDA():
    """Manages routing and flow installation using PyCUDA GPU acceleration"""
    
    def __init__(self, topo_file=None, onos_ip='127.0.0.1', port=8181, 
                 block_size=256, grid_multiplier=1, batch_size=5000, max_path_length=32):
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
        
        # GPU configuration parameters
        self.block_size = block_size
        self.grid_multiplier = grid_multiplier
        self.batch_size = batch_size
        self.max_path_length = max_path_length

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
        """Build adjacency matrix for PyCUDA"""
        if not self.topology_data:
            print("Warning: No topology data available, trying to reload...")
            self.topology_data = self.load_topology_data()
            if not self.topology_data:
                raise ValueError("Topology data required for PyCUDA - ensure network is created first")
        
        if not self.hosts:
            raise ValueError("No hosts found in ONOS - ensure network is created and router.update() is called")
        
        # Collect all unique nodes
        all_nodes = set()
        
        # Add hosts
        for host in self.hosts:
            all_nodes.add(host['mac'])
        
        # Add switches (from hosts and links)
        for host in self.hosts:
            switch_id = host['locations'][0]['elementId']
            all_nodes.add(switch_id)
        
        for link in self.links:
            all_nodes.add(link['src']['device'])
            all_nodes.add(link['dst']['device'])
        
        all_nodes = sorted(list(all_nodes))
        n = len(all_nodes)
        
        # Create mappings
        self.node_to_index = {node: i for i, node in enumerate(all_nodes)}
        self.index_to_node = {i: node for i, node in enumerate(all_nodes)}
        
        # Initialize matrix with infinity (float32 to avoid overflow)
        INFNTY = 1e9
        adjacency_matrix = np.full((n, n), INFNTY, dtype=np.float32)
        
        # Diagonal = 0 (distance from node to itself)
        np.fill_diagonal(adjacency_matrix, 0)
        
        # Add host-switch connections
        for host in self.hosts:
            host_mac = host['mac']
            switch_id = host['locations'][0]['elementId']
            host_idx = self.node_to_index[host_mac]
            switch_idx = self.node_to_index[switch_id]
            
            weight = HOST_SWITCH_WEIGHT
            adjacency_matrix[host_idx, switch_idx] = weight
            adjacency_matrix[switch_idx, host_idx] = weight
        
        # Add switch-switch connections
        for link in self.links:
            src = link['src']['device']
            dst = link['dst']['device']
            src_idx = self.node_to_index[src]
            dst_idx = self.node_to_index[dst]
            
            clean_src = self.clean_dpid(src)
            clean_dst = self.clean_dpid(dst)
            
            distance = self.find_distance(clean_src, clean_dst)
            if distance is not None:
                weight = distance
                adjacency_matrix[src_idx, dst_idx] = weight
                adjacency_matrix[dst_idx, src_idx] = weight
            else:
                weight = 1.0
                adjacency_matrix[src_idx, dst_idx] = weight
                adjacency_matrix[dst_idx, src_idx] = weight
                print(f"Using default weight for link {clean_src}-{clean_dst} = {weight}")
        
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
        total_flows = len(flows_data)
        all_results = []
        
        for i in range(0, total_flows, batch_size):
            batch = flows_data[i:i + batch_size]
            try:
                batch_result = self.api.push_flows_batch(batch)
                if batch_result:
                    all_results.extend(batch_result)
            except Exception as e:
                pass
        
        return all_results

    def install_all_routes(self, parallel=True):
        """
        Install all routes using GPU-accelerated processing (default method)
        
        Args:
            parallel (bool): Ignored - GPU acceleration is always used
        """
        
        # Build adjacency matrix and get distance matrix from GPU
        adjacency_matrix = self.build_adjacency_matrix()
        V = len(self.node_to_index)
        
        # Get all-pairs shortest distances using GPU Dijkstra
        distance_matrix, _ = dijkstra_parallel_pycuda(V, adjacency_matrix)
        
        if distance_matrix is None:
            print("Failed to compute distance matrix on GPU")
            return []
        
        # Extract MAC addresses from host dictionaries
        unique_hosts = {host['ipAddresses'][0]: host for host in self.hosts}
        host_macs = [host['mac'] for host in unique_hosts.values()]
        
        if len(host_macs) < 2:
            print("Not enough hosts for routing")
            return []
        
        # Generate all host pairs (MAC addresses)
        host_pairs = list(combinations(host_macs, 2))
        
        # GPU-accelerated flow generation
        start_time = time.time()
        unique_flows_final = self._generate_flows_gpu_accelerated(
            host_pairs, distance_matrix, adjacency_matrix
        )
        gpu_time = time.time() - start_time
        
        # Convert to flows and push to ONOS
        flows_data = self.generate_flows(list(unique_flows_final))
        
        if flows_data:
            self.push_flows_to_onos(flows_data)
        
        return flows_data

    def _generate_flows_gpu_accelerated(self, host_pairs, distance_matrix, adjacency_matrix):
        """Generate flows using GPU acceleration with configurable parameters"""
        unique_flows_final = set()
        
        # Use configurable batch size
        batch_size = min(self.batch_size, len(host_pairs))
        
        for i in range(0, len(host_pairs), batch_size):
            batch = host_pairs[i:i + batch_size]
            
            # GPU batch path reconstruction with custom configuration
            valid_paths = reconstruct_paths_batch_gpu(
                batch, distance_matrix, adjacency_matrix, 
                self.node_to_index, self.index_to_node,
                block_size=self.block_size,
                grid_multiplier=self.grid_multiplier,
                max_path_length=self.max_path_length
            )
            
            # Generate flows from GPU-computed paths (minimal CPU work)
            for j, path_nodes in enumerate(valid_paths):
                if j < len(batch) and len(path_nodes) >= 3:
                    source_mac, target_mac = batch[j]
                    self._add_bidirectional_flows(path_nodes, source_mac, target_mac, unique_flows_final)
        
        return unique_flows_final

    def _add_bidirectional_flows(self, path_nodes, source_mac, target_mac, flows_set):
        """Add flows for both directions efficiently"""
        if len(path_nodes) < 3:
            return
        
        # Process both directions at once
        directions = [
            (path_nodes, source_mac, target_mac),
            (list(reversed(path_nodes)), target_mac, source_mac)
        ]
        
        for direction_path, src_mac, dst_mac in directions:
            for i in range(1, len(direction_path) - 1):
                current_switch = direction_path[i]
                if current_switch in self.switches_set:
                    prev_node = direction_path[i-1]
                    next_node = direction_path[i+1]
                    
                    in_port = self.port_map.get((current_switch, prev_node))
                    out_port = self.port_map.get((current_switch, next_node))
                    
                    if in_port and out_port:
                        flows_set.add((
                            current_switch, in_port, out_port, 
                            DEFAULT_PRIORITY, dst_mac, src_mac
                        ))