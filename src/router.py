import networkx as nx
from itertools import combinations
import time
import json
import os
import concurrent.futures
import math

# Detect if Mininet is available
try:
    import mininet
    from onos_api import OnosApi
    MININET_AVAILABLE = True
except ImportError:
    from onos_api_mock import OnosApiMock as OnosApi
    MININET_AVAILABLE = False
    print("Router: Using mock ONOS API")

# Router configuration constants
DEFAULT_PRIORITY = 10
HOST_SWITCH_WEIGHT = 0.1
MAX_WORKERS = 16
BATCH_SIZE = 1000

def process_batch_worker(host_pairs_batch, graph, port_map, host_lookup, switches_set, precomputed_switch_distances):
    """Process a batch of host pairs for parallel route computation"""
    
    def clean_dpid(dpid):
        """Remove 'of:' prefix from DPID if present"""
        return dpid[3:] if dpid.startswith('of:') else dpid

    def get_host_switch(host_mac):
        """Get switch ID that host is connected to"""
        for switch_id in switches_set:
            if (switch_id, host_mac) in port_map:
                return switch_id
        return None

    def get_switch_for_node(node):
        """Get switch for node (host MAC or switch ID)"""
        if node in host_lookup:
            return get_host_switch(node)
        elif node in switches_set:
            return node
        return None

    def heuristic_function(node1, node2):
        """A* heuristic using precomputed switch distances"""
        if node1 == node2:
            return 0.0
        
        if not precomputed_switch_distances:
            return 0.0
        
        switch1 = get_switch_for_node(node1)
        switch2 = get_switch_for_node(node2)
        
        if not switch1 or not switch2:
            return 0.0
        
        clean_switch1 = clean_dpid(switch1)
        clean_switch2 = clean_dpid(switch2)
        switch_distance = precomputed_switch_distances.get(clean_switch1, {}).get(clean_switch2, 0.0)
        
        cost = 0.0
        if node1 in host_lookup:
            cost += HOST_SWITCH_WEIGHT
        if node2 in host_lookup:
            cost += HOST_SWITCH_WEIGHT
        
        return cost + switch_distance

    all_flows = set()
    
    for source_mac, target_mac in host_pairs_batch:
        source_ip = host_lookup.get(source_mac)
        target_ip = host_lookup.get(target_mac)
        
        if source_ip == target_ip:
            continue

        try:
            path = nx.astar_path(
                graph, 
                source=source_mac, 
                target=target_mac,
                heuristic=heuristic_function,
                weight='weight'
            )

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
        except nx.NetworkXNoPath:
            continue
    
    return list(all_flows)

class Router():
    """Manages routing and flow installation using A* algorithm"""
    
    def __init__(self, onos_ip='127.0.0.1', port=8181):
        if MININET_AVAILABLE:
            self.api = OnosApi(onos_ip, port)
        else:
            self.api = OnosApi()
            print(f"Router: Initialized with mock ONOS API")
        
        self.hosts = []
        self.switches = []
        self.links = []
        self.topology_data = self.load_topology_data()
        
        self.mac_to_ip = {}
        self.mac_to_location = {}
        self.port_map = {}
        self.switches_set = set()
        
        self.path_cache = {}
        self.precomputed_switch_distances = {}

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
                    print(f"Router: Loaded {file_type} topology data from {filename}")
                    return data
                except Exception as e:
                    print(f"Error loading {filename}: {e}")
                    continue
        
        print("Router: No topology data file found")
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

    def _precompute_all_switch_distances(self, graph):
        """Precompute shortest path distances between all switch pairs"""
        print("Precomputing all switch-to-switch distances...")
        start_time = time.time()
        
        # Extract switch-only subgraph
        switch_nodes = [node for node in graph.nodes() if node in self.switches_set]
        switch_subgraph = graph.subgraph(switch_nodes).copy()
        
        if not switch_nodes:
            print("No switches found for precomputation")
            return {}
        
        try:
            # Use Dijkstra all-pairs for efficiency
            all_shortest_paths = dict(nx.all_pairs_dijkstra_path_length(switch_subgraph, weight='weight'))
            
            # Convert to nested dictionary with clean DPIDs
            precomputed_distances = {}
            for source_switch in all_shortest_paths:
                clean_source = self.clean_dpid(source_switch)
                precomputed_distances[clean_source] = {}
                
                for target_switch, distance in all_shortest_paths[source_switch].items():
                    clean_target = self.clean_dpid(target_switch)
                    precomputed_distances[clean_source][clean_target] = distance
            
            calc_time = time.time() - start_time
            total_pairs = len(switch_nodes) * len(switch_nodes)
            print(f"Precomputed {total_pairs} switch distance pairs in {calc_time:.3f}s")
            
            return precomputed_distances
            
        except Exception as e:
            print(f"Error in switch distance precomputation: {e}")
            return {}

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

    def build_graph(self):
        """Build topology graph with optimized weights"""
        if not self.topology_data:
            print("Warning: No topology data available, trying to reload...")
            self.topology_data = self.load_topology_data()
            if not self.topology_data:
                raise ValueError("Topology data required for A* - ensure network is created first")
        
        G = nx.Graph()
        
        if not self.hosts:
            raise ValueError("No hosts found in ONOS - ensure network is created and router.update() is called")
        
        # Add host-switch connections with fixed weight
        for host in self.hosts:
            host_mac = host['mac']
            switch_id = host['locations'][0]['elementId']
            G.add_edge(host_mac, switch_id, weight=HOST_SWITCH_WEIGHT)
        
        if not self.links:
            raise ValueError("No switch links found")
        
        # Add switch-switch connections with real distance
        for link in self.links:
            src = link['src']['device']
            dst = link['dst']['device']
            clean_src = self.clean_dpid(src)
            clean_dst = self.clean_dpid(dst)
            
            distance = self.find_distance(clean_src, clean_dst)
            if distance is not None:
                G.add_edge(src, dst, weight=distance)
            else:
                G.add_edge(src, dst, weight=1.0)
                print(f"Using default weight for link {clean_src}-{clean_dst}")
        
        print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        return G

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
            print(f"{mode} topology updated: {len(self.hosts)} hosts, {len(self.switches)} switches, {len(self.links)} links")
        except Exception as e:
            print(f"Error updating topology: {e}")
            # Initialize empty data structures if API fails
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

    def heuristic_function(self, node1, node2):
        """Ultra-fast O(1) heuristic using precomputed switch distances"""
        if node1 == node2:
            return 0.0
        
        if not self.precomputed_switch_distances:
            return 0.0
        
        # Get switches for both nodes
        switch1 = self.get_switch_for_node(node1)
        switch2 = self.get_switch_for_node(node2)
        
        if not switch1 or not switch2:
            return 0.0
        
        # Clean switch IDs and O(1) lookup
        clean_switch1 = self.clean_dpid(switch1)
        clean_switch2 = self.clean_dpid(switch2)
        switch_distance = self.precomputed_switch_distances.get(clean_switch1, {}).get(clean_switch2, 0.0)
        
        # Add host-switch costs
        cost = 0.0
        if node1 in self.mac_to_ip:
            cost += HOST_SWITCH_WEIGHT
        if node2 in self.mac_to_ip:
            cost += HOST_SWITCH_WEIGHT
        
        return cost + switch_distance

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
        """Install all routes using A* with precomputed distances
        
        Args:
            parallel (bool): If True, use ProcessPoolExecutor; if False, use sequential processing
        """
        api_mode = "Mock" if not MININET_AVAILABLE else "Real"
        processing_mode = "ProcessPoolExecutor parallel" if parallel else "sequential"
        print(f"Starting {processing_mode} route installation using {api_mode} ONOS API...")
        
        start_time = time.time()
        graph = self.build_graph()
        
        if not graph or not graph.nodes:
            print("Graph not built or is empty")
            return []

        # Precompute distances
        precomputed_switch_distances = self._precompute_all_switch_distances(graph)
        if not parallel:
            self.precomputed_switch_distances = precomputed_switch_distances
        
        # Get unique hosts
        unique_hosts = {host['ipAddresses'][0]: host for host in self.hosts}
        host_macs = [host['mac'] for host in unique_hosts.values()]
        
        if len(host_macs) < 2:
            print("Insufficient hosts to create routes")
            return []

        # Create host pairs
        host_pairs = list(combinations(host_macs, 2))
        unique_flows_final = set()

        if parallel:
            # Parallel processing with ProcessPoolExecutor
            batch_size = max(BATCH_SIZE, len(host_pairs) // (MAX_WORKERS * 2))
            host_batches = [host_pairs[i:i + batch_size] for i in range(0, len(host_pairs), batch_size)]

            print(f"Processing {len(host_pairs)} pairs in {len(host_batches)} batches with {MAX_WORKERS} processes")

            with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
                # Submit all batches with all necessary data as parameters
                futures = [
                    executor.submit(
                        process_batch_worker,
                        batch,
                        graph,
                        self.port_map,
                        self.mac_to_ip,
                        self.switches_set,
                        precomputed_switch_distances
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
            # Sequential processing with path caching
            for source_mac, target_mac in host_pairs:
                source_ip = self.mac_to_ip.get(source_mac)
                target_ip = self.mac_to_ip.get(target_mac)
                
                if source_ip == target_ip:
                    continue
                
                # Use ordered tuple as cache key
                pair_key = tuple(sorted((source_mac, target_mac)))
                
                if pair_key in self.path_cache:
                    path = self.path_cache[pair_key]
                    if (source_mac, target_mac) != pair_key:
                        path = list(reversed(path))
                else:
                    try:
                        path = nx.astar_path(
                            graph, 
                            source=source_mac, 
                            target=target_mac,
                            heuristic=self.heuristic_function,
                            weight='weight'
                        )
                        self.path_cache[pair_key] = path
                    except nx.NetworkXNoPath:
                        print(f"No path found between {source_mac} and {target_mac}")
                        continue
                
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
            print("No flows generated")
            return []

        calc_time = time.time() - start_time
        print(f"{processing_mode} A* calculation: {calc_time:.2f}s")
        
        api_start = time.time()
        api_results = self.push_flows_to_onos(all_flows)
        api_time = time.time() - api_start
        
        print(f"{processing_mode} installation completed: {len(api_results)} flows in {calc_time + api_time:.2f}s using {api_mode} API")
        return api_results

    def install_all_routes_sequential(self):
        """Install routes using sequential A* (wrapper for backward compatibility)"""
        return self.install_all_routes(parallel=False)
    
    def install_all_routes_parallel(self):
        """Install routes using ProcessPoolExecutor (wrapper for backward compatibility)"""
        return self.install_all_routes(parallel=True)