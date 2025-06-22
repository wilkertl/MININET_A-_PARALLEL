import networkx as nx
from itertools import combinations
import time
import json
import os
import concurrent.futures
import math
import logging
from datetime import datetime

from onos_api import OnosApi 

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variables for subprocesses
GRAPH = None
PORT_MAP = None
HOST_LOOKUP = None
SWITCHES = None

# Class constants
DEFAULT_PRIORITY = 10
HOST_SWITCH_WEIGHT = 0.1
MAX_WORKERS = 8
BATCH_SIZE = 100

def init_worker(graph, port_map, host_lookup, switches):
    """Initialize global variables in subprocesses"""
    global GRAPH, PORT_MAP, HOST_LOOKUP, SWITCHES
    GRAPH = graph
    PORT_MAP = port_map
    HOST_LOOKUP = host_lookup
    SWITCHES = switches

def find_port_global(src, dst):
    """Find connection port using global map"""
    return PORT_MAP.get((src, dst))

def get_host_ip_from_mac_global(mac):
    """Convert host MAC to IP using global lookup"""
    return HOST_LOOKUP.get(mac)

def process_batch_global(host_pairs_batch):
    """Process a batch of host pairs using global variables"""
    all_flows = set()
    
    for source_mac, target_mac in host_pairs_batch:
        source_ip = get_host_ip_from_mac_global(source_mac)
        target_ip = get_host_ip_from_mac_global(target_mac)
        
        if source_ip == target_ip:
            continue

        try:
            path = nx.astar_path(
                GRAPH, 
                source=source_mac, 
                target=target_mac,
                heuristic=lambda n1, n2: 0.0,  # Simplified heuristic
                weight='weight'
            )

            for direction_path in [path, list(reversed(path))]:
                dst_mac = target_mac if direction_path == path else source_mac
                src_mac = source_mac if direction_path == path else target_mac
                
                for i in range(1, len(direction_path) - 1):
                    current_switch = direction_path[i]
                    if current_switch in SWITCHES:
                        prev_node = direction_path[i-1]
                        next_node = direction_path[i+1]
                        
                        in_port = find_port_global(current_switch, prev_node)
                        out_port = find_port_global(current_switch, next_node)
                        
                        if in_port and out_port:
                            all_flows.add((
                                current_switch, in_port, out_port, 
                                DEFAULT_PRIORITY, dst_mac, src_mac
                            ))
        except nx.NetworkXNoPath:
            logger.warning(f"No path found between {source_mac} and {target_mac}")
            continue
    
    return list(all_flows)

class Router():
    def __init__(self, onos_ip='127.0.0.1', port=8181):
        self.api = OnosApi(onos_ip, port)
        self.hosts = []
        self.switches = []
        self.links = []
        self.topology_data = self.load_topology_data()
        
        # Fast lookups
        self.mac_to_ip = {}
        self.mac_to_location = {}
        self.port_map = {}
        self.switches_set = set()
        
        # A* path cache
        self.path_cache = {}

    def load_topology_data(self):
        """Load topology data from JSON file"""
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'topology_data.json')
        
        if not os.path.exists(json_path):
            logger.warning("topology_data.json file not found.")
            return None
            
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except Exception as e:
            logger.error(f"Error loading topology_data.json: {e}")
            return None

    def clean_dpid(self, dpid):
        """Remove 'of:' prefix from DPID if present"""
        return dpid[3:] if dpid.startswith('of:') else dpid

    def find_distance(self, node1, node2):
        """Search for distance between two nodes in topology JSON"""
        if node1 == node2:
            return 0.0
            
        if not self.topology_data or 'distances' not in self.topology_data:
            logger.error(f"Data not available for {node1}-{node2}")
            return None
        
        distances = self.topology_data['distances']
        possible_keys = [f"{node1}-{node2}", f"{node2}-{node1}"]
        
        for key in possible_keys:
            if key in distances:
                return distances[key]
        
        logger.warning(f"Distance not found between {node1} and {node2}")
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
            logger.error(f"Disconnected hosts found: {disconnected_hosts}")
            return False
        
        return True

    def build_graph(self):
        """Build topology graph with optimized weights"""
        if not self.topology_data:
            raise ValueError("Topology data required for A*")
        
        G = nx.Graph()
        
        if not self.hosts:
            raise ValueError("No hosts found in ONOS")
        
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
                # Use default weight if distance not available
                G.add_edge(src, dst, weight=1.0)
                logger.warning(f"Using default weight for link {clean_src}-{clean_dst}")
        
        logger.info(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        return G

    def update(self):
        """Update network topology from ONOS"""
        self.hosts = self.api.get_hosts()
        self.switches = self.api.get_switches()
        self.links = self.api.get_links()
        
        # Build lookups
        self.build_lookups()
        
        # Validate connectivity
        self.validate_hosts_connectivity()
        
        # Clear path cache
        self.path_cache.clear()
        
        logger.info(f"Topology updated: {len(self.hosts)} hosts, {len(self.switches)} switches, {len(self.links)} links")

    def find_port(self, src, dst):
        """Find connection port using port map"""
        return self.port_map.get((src, dst))
    
    def get_host_ip_from_mac(self, mac):
        """Convert host MAC to IP using lookup"""
        return self.mac_to_ip.get(mac)

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

    def push_flows_to_onos(self, flows_data, batch_size=1000):
        """Send flows to ONOS in sequential batches"""
        batches = [flows_data[i:i + batch_size] for i in range(0, len(flows_data), batch_size)]
        
        all_results = []
        for i, batch in enumerate(batches):
            batch_result = self.api.push_flows_batch(batch)
            all_results.extend(batch_result)
        
        return all_results

    def install_all_routes(self):
        """Install routes using sequential A* with path caching"""
        logger.info("Starting sequential route installation...")
        
        start_time = time.time()
        graph = self.build_graph()
        unique_flows_final = set()

        # Get unique hosts
        unique_hosts = {host['ipAddresses'][0]: host for host in self.hosts}
        host_macs = [host['mac'] for host in unique_hosts.values()]
        
        if len(host_macs) < 2:
            logger.warning("Insufficient hosts to create routes")
            return []

        # Process host pairs
        for source_mac, target_mac in combinations(host_macs, 2):
            source_ip = self.get_host_ip_from_mac(source_mac)
            target_ip = self.get_host_ip_from_mac(target_mac)
            
            if source_ip == target_ip:
                continue
            
            # Check path cache
            cache_key = f"{source_mac}-{target_mac}"
            reverse_key = f"{target_mac}-{source_mac}"
            
            if cache_key in self.path_cache:
                path = self.path_cache[cache_key]
            elif reverse_key in self.path_cache:
                path = list(reversed(self.path_cache[reverse_key]))
            else:
                try:
                    path = nx.astar_path(
                        graph, 
                        source=source_mac, 
                        target=target_mac,
                        heuristic=lambda n1, n2: 0.0,  # Simplified heuristic
                        weight='weight'
                    )
                    self.path_cache[cache_key] = path
                except nx.NetworkXNoPath:
                    logger.warning(f"No path found between {source_mac} and {target_mac}")
                    continue
            
            # Generate flows for both directions
            for direction_path in [path, list(reversed(path))]:
                dst_mac = target_mac if direction_path == path else source_mac
                src_mac = source_mac if direction_path == path else target_mac
                
                for i in range(1, len(direction_path) - 1): 
                    current_switch = direction_path[i]
                    if current_switch in self.switches_set:  
                        in_port = self.find_port(current_switch, direction_path[i-1])  
                        out_port = self.find_port(current_switch, direction_path[i+1])  
                        
                        if in_port and out_port:
                            unique_flows_final.add((
                                current_switch, in_port, out_port, 
                                DEFAULT_PRIORITY, dst_mac, src_mac
                            ))

        # Generate, save and send flows
        all_flows = self.generate_flows(list(unique_flows_final))
        
        if not all_flows:
            logger.warning("No flows generated")
            return []

        calc_time = time.time() - start_time
        logger.info(f"Sequential A* calculation: {calc_time:.2f}s")
        
        api_start = time.time()
        results = self.push_flows_to_onos(all_flows)
        api_time = time.time() - api_start

        logger.info(f"Sequential installation completed: {len(results)} flows in {calc_time + api_time:.2f}s")
        return results

    def install_all_routes_parallel(self):
        """Install all routes using parallel A* with ProcessPoolExecutor"""
        logger.info("Starting parallel route installation...")

        start_time = time.time()
        graph = self.build_graph()

        if not graph or not graph.nodes:
            logger.error("Graph not built or is empty")
            return []

        # Get unique hosts
        unique_hosts = {host['ipAddresses'][0]: host for host in self.hosts}
        host_macs = [host['mac'] for host in unique_hosts.values()]
        
        if len(host_macs) < 2:
            logger.warning("Insufficient hosts to create routes")
            return []

        # Create host pairs and batches
        host_pairs = list(combinations(host_macs, 2))
        batch_size = max(BATCH_SIZE, len(host_pairs) // MAX_WORKERS)
        host_batches = [host_pairs[i:i + batch_size] for i in range(0, len(host_pairs), batch_size)]

        logger.info(f"Processing {len(host_pairs)} pairs in {len(host_batches)} batches with {MAX_WORKERS} workers")

        unique_flows_final = set()
        
        # Execute parallel processing
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=MAX_WORKERS,
            initializer=init_worker,
            initargs=(graph, self.port_map, self.mac_to_ip, self.switches_set)
        ) as executor:
            results = executor.map(process_batch_global, host_batches)
            
            for flow_list in results:
                unique_flows_final.update(flow_list)

        # Generate, save and send flows
        all_flows = self.generate_flows(list(unique_flows_final))

        if not all_flows:
            logger.warning("No flows generated")
            return []

        calc_time = time.time() - start_time
        logger.info(f"Parallel A* calculation: {calc_time:.2f}s")
        
        api_start = time.time()
        api_results = self.push_flows_to_onos(all_flows)
        api_time = time.time() - api_start
        
        logger.info(f"Parallel installation completed: {len(api_results)} flows in {calc_time + api_time:.2f}s")
        return api_results