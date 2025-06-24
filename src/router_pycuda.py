"""
Router using PyCUDA parallel Dijkstra implementation
GPU-accelerated routing for large-scale networks
"""

import time
import json
import os
import numpy as np
from itertools import combinations
import concurrent.futures

# Import PyCUDA Dijkstra implementation
from dijkstra import dijkstra_parallel_pycuda, PYCUDA_AVAILABLE

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

def process_batch_worker_pycuda(host_pairs_batch, distance_matrix, node_to_index, index_to_node, 
                               adjacency_lookup, port_map, host_lookup, switches_set):
    """Process a batch of host pairs for parallel route computation using PyCUDA results"""
    
    def find_shortest_path_worker(source_node, target_node, distance_matrix, adjacency_lookup, 
                                 node_to_index, index_to_node):
        """Find shortest path using PyCUDA distance matrix - OPTIMIZED WORKER"""
        if source_node not in node_to_index or target_node not in node_to_index:
            return None
        
        source_idx = node_to_index[source_node]
        target_idx = node_to_index[target_node]
        
        INFNTY = 1e9
        if distance_matrix[source_idx, target_idx] >= INFNTY:
            return None
            
        if source_idx == target_idx:
            return [source_node]
        
        # Fast greedy path reconstruction
        path = [source_node]
        current_node = source_node
        current_idx = source_idx
        visited = {source_node}
        
        for _ in range(8):  # Limit hops for performance
            if current_idx == target_idx:
                break
                
            best_next_node = None
            best_next_idx = -1
            min_distance = float('inf')
            
            if current_node in adjacency_lookup:
                for neighbor_node, _ in adjacency_lookup[current_node]:
                    if neighbor_node in visited or neighbor_node not in node_to_index:
                        continue
                    
                    neighbor_idx = node_to_index[neighbor_node]
                    remaining_distance = distance_matrix[neighbor_idx, target_idx]
                    
                    if remaining_distance < INFNTY and remaining_distance < min_distance:
                        min_distance = remaining_distance
                        best_next_node = neighbor_node
                        best_next_idx = neighbor_idx
            
            if best_next_node is None:
                return None
            
            current_node = best_next_node
            current_idx = best_next_idx
            path.append(current_node)
            visited.add(current_node)
        
        if current_idx == target_idx:
            return path
        
        return None
    
    all_flows = set()
    
    for source_mac, target_mac in host_pairs_batch:
        source_ip = host_lookup.get(source_mac)
        target_ip = host_lookup.get(target_mac)
        
        if source_ip == target_ip:
            continue
        
        path = find_shortest_path_worker(source_mac, target_mac, distance_matrix, 
                                       adjacency_lookup, node_to_index, index_to_node)
        
        if not path or len(path) < 3:
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

class RouterPyCUDA():
    """Manages routing and flow installation using PyCUDA Dijkstra implementation"""
    
    def __init__(self, onos_ip='127.0.0.1', port=8181):
        if MININET_AVAILABLE:
            self.api = OnosApi(onos_ip, port)
        else:
            self.api = OnosApi()
        
        if not PYCUDA_AVAILABLE:
            raise RuntimeError("PyCUDA not available! Install with: pip install pycuda")
        
        self.hosts = []
        self.switches = []
        self.links = []
        self.topology_data = self.load_topology_data()
        
        self.mac_to_ip = {}
        self.mac_to_location = {}
        self.port_map = {}
        self.switches_set = set()
        
        # Node mapping for adjacency matrix
        self.node_to_index = {}
        self.index_to_node = {}
        
        self.path_cache = {}

    def load_topology_data(self):
        """Load topology data from JSON file with automatic fallback"""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        possible_files = []
        if not MININET_AVAILABLE:
            possible_files.append(('topology_data_mock.json', 'mock'))
            possible_files.append(('topology_data.json', 'real'))
        else:
            possible_files.append(('topology_data.json', 'real'))
            possible_files.append(('topology_data_mock.json', 'mock'))
        
        for filename, file_type in possible_files:
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
        
        # Check matrix integrity
        max_val = np.max(adjacency_matrix[adjacency_matrix != INFNTY])
        min_val = np.min(adjacency_matrix[adjacency_matrix > 0])
        
        return adjacency_matrix

    def update(self):
        """Update network topology from ONOS"""
        try:
            self.hosts = self.api.get_hosts()
            self.switches = self.api.get_switches()
            self.links = self.api.get_links()
            
            self.build_lookups()
            self.validate_hosts_connectivity()
            self.path_cache.clear()
            
            mode = "Mock" if not MININET_AVAILABLE else "Real"
        except Exception as e:
            print(f"Error updating topology: {e}")
            self.hosts = []
            self.switches = []
            self.links = []

    def get_host_switch(self, host_mac):
        """Get switch ID that host is connected to"""
        for switch_id in self.switches_set:
            if (switch_id, host_mac) in self.port_map:
                return switch_id
        return None

    def get_switch_for_node(self, node):
        """Get the switch associated with a node (host MAC or switch ID)"""
        if node in self.mac_to_ip:
            return self.get_host_switch(node)
        elif node in self.switches_set:
            return node
        return None

    def build_adjacency_lookup(self):
        """Build fast adjacency lookup for path reconstruction"""
        adjacency_lookup = {}
        
        # Add host-switch connections
        for host in self.hosts:
            host_mac = host['mac']
            switch_id = host['locations'][0]['elementId']
            
            if host_mac not in adjacency_lookup:
                adjacency_lookup[host_mac] = []
            if switch_id not in adjacency_lookup:
                adjacency_lookup[switch_id] = []
                
            adjacency_lookup[host_mac].append((switch_id, HOST_SWITCH_WEIGHT))
            adjacency_lookup[switch_id].append((host_mac, HOST_SWITCH_WEIGHT))
        
        # Add switch-switch connections
        for link in self.links:
            src = link['src']['device']
            dst = link['dst']['device']
            clean_src = self.clean_dpid(src)
            clean_dst = self.clean_dpid(dst)
            
            distance = self.find_distance(clean_src, clean_dst)
            weight = distance if distance is not None else 1.0
            
            if src not in adjacency_lookup:
                adjacency_lookup[src] = []
            if dst not in adjacency_lookup:
                adjacency_lookup[dst] = []
                
            adjacency_lookup[src].append((dst, weight))
            adjacency_lookup[dst].append((src, weight))
        
        return adjacency_lookup

    def find_shortest_path_pycuda(self, source_node, target_node, distance_matrix, adjacency_lookup):
        """Find shortest path using PyCUDA distance matrix - OPTIMIZED"""
        if source_node not in self.node_to_index or target_node not in self.node_to_index:
            return None
        
        source_idx = self.node_to_index[source_node]
        target_idx = self.node_to_index[target_node]
        
        if source_idx == target_idx:
            return [source_node]
        
        # Fast path reconstruction using greedy approach
        path = [source_node]
        current_node = source_node
        current_idx = source_idx
        visited = {source_node}
        
        INFNTY = 1e9
        max_hops = 10  # Limit path length for performance
        
        for _ in range(max_hops):
            if current_idx == target_idx:
                break
                
            best_next_node = None
            best_next_idx = -1
            min_distance = float('inf')
            
            # Find best neighbor (lowest remaining distance to target)
            if current_node in adjacency_lookup:
                for neighbor_node, _ in adjacency_lookup[current_node]:
                    if neighbor_node in visited or neighbor_node not in self.node_to_index:
                        continue
                    
                    neighbor_idx = self.node_to_index[neighbor_node]
                    remaining_distance = distance_matrix[neighbor_idx, target_idx]
                    
                    if remaining_distance < INFNTY and remaining_distance < min_distance:
                        min_distance = remaining_distance
                        best_next_node = neighbor_node
                        best_next_idx = neighbor_idx
            
            if best_next_node is None:
                return None
            
            current_node = best_next_node
            current_idx = best_next_idx
            path.append(current_node)
            visited.add(current_node)
        
        if current_idx == target_idx:
            return path
        
        return None

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
        """Install all routes using PyCUDA GPU parallel Dijkstra algorithm
        
        Note: PyCUDA is always parallel (GPU-based). The parallel parameter controls
        whether to use ProcessPoolExecutor for host pair processing, but GPU computation
        is always parallel.
        
        Args:
            parallel (bool): If True, use ProcessPoolExecutor for host pair processing
        """
        api_mode = "Mock" if not MININET_AVAILABLE else "Real"
        processing_mode = "GPU+CPU parallel" if parallel else "GPU+CPU sequential"
        start_time = time.time()
        
        # Build adjacency matrix for PyCUDA
        adjacency_matrix = self.build_adjacency_matrix()
        if adjacency_matrix is None:
            return []
        
        V = adjacency_matrix.shape[0]
        
        # Execute PyCUDA Dijkstra (ALWAYS parallel on GPU)
        gpu_start = time.time()
        distance_matrix, _ = dijkstra_parallel_pycuda(V, adjacency_matrix)
        gpu_time = time.time() - gpu_start
        
        if distance_matrix is None:
            return []
        
        # Build adjacency lookup for path reconstruction
        adjacency_lookup = self.build_adjacency_lookup()
        
        # Get unique hosts
        unique_hosts = {host['ipAddresses'][0]: host for host in self.hosts}
        host_macs = [host['mac'] for host in unique_hosts.values()]
        
        if len(host_macs) < 2:
            return []

        # Create host pairs
        host_pairs = list(combinations(host_macs, 2))
        unique_flows_final = set()
        
        if parallel:
            # Parallel host pair processing with ProcessPoolExecutor
            batch_size = max(BATCH_SIZE, len(host_pairs) // (MAX_WORKERS * 2))
            host_batches = [host_pairs[i:i + batch_size] for i in range(0, len(host_pairs), batch_size)]

            with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = [
                    executor.submit(
                        process_batch_worker_pycuda,
                        batch,
                        distance_matrix,
                        self.node_to_index,
                        self.index_to_node,
                        adjacency_lookup,
                        self.port_map,
                        self.mac_to_ip,
                        self.switches_set
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
        else:
            # Sequential host pair processing (but GPU Dijkstra is still parallel)
            paths_found = 0
            paths_failed = 0
            
            for i, (source_mac, target_mac) in enumerate(host_pairs):
                source_ip = self.mac_to_ip.get(source_mac)
                target_ip = self.mac_to_ip.get(target_mac)
                
                if source_ip == target_ip:
                    continue
                
                # Use PyCUDA distance matrix for path reconstruction
                path = self.find_shortest_path_pycuda(source_mac, target_mac, distance_matrix, adjacency_lookup)
                
                if not path or len(path) < 3:
                    paths_failed += 1
                    continue
                else:
                    paths_found += 1
                
                # Generate flows for both directions
                for direction_path in [path, list(reversed(path))]:
                    dst_mac = target_mac if direction_path == path else source_mac
                    src_mac = source_mac if direction_path == path else target_mac
                    
                    for i in range(1, len(direction_path) - 1): 
                        current_switch = direction_path[i]
                        if current_switch in self.switches_set:  
                            in_port = self.port_map.get((current_switch, direction_path[i-1]))
                            out_port = self.port_map.get((current_switch, direction_path[i+1]))
                            
                            if in_port and out_port:
                                unique_flows_final.add((
                                    current_switch, in_port, out_port, 
                                    DEFAULT_PRIORITY, dst_mac, src_mac
                                ))
            
        # Generate and push flows
        all_flows = self.generate_flows(list(unique_flows_final))

        if not all_flows:
            return []

        calc_time = time.time() - start_time
        
        api_start = time.time()
        api_results = self.push_flows_to_onos(all_flows)
        api_time = time.time() - api_start
        
        return all_flows

    def install_all_routes_pycuda_parallel(self):
        """Install routes using PyCUDA GPU with parallel host processing (recommended)"""
        return self.install_all_routes(parallel=True)
    
    def install_all_routes_pycuda_sequential(self):
        """Install routes using PyCUDA GPU with sequential host processing"""
        return self.install_all_routes(parallel=False)