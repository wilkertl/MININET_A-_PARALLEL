import os
import math
import random
import networkx as nx
import json
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import RemoteController
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from time import sleep
from dotenv import load_dotenv
from threading import Lock

load_dotenv()
random.seed(42)

# Topology configurations
MIN_BACKBONE_BW_MBPS = 30.0  
MAX_BACKBONE_BW_MBPS = 100.0  
PROPAGATION_SPEED_KM_PER_MS = 200  
MIN_HOSTS_PER_EDGE_SWITCH = 1
MAX_HOSTS_PER_EDGE_SWITCH = 7
EDGE_SWITCH_DEGREE_THRESHOLD = 2  
LOW_LINK_CHANCE = 0.30 
HOST_BW_MBPS = 10.0

def make_dpid(index):
    """Generates a 16-digit hexadecimal formatted DPID"""
    return format(index, '016x')

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates geodesic distance in km"""
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def generate_network_topology_data(topo, net):
    """Generates simplified topology data for JSON file"""
    if hasattr(topo, 'get_topology_data'):
        return topo.get_topology_data(net)
    else:
        return {"distances": {}, "bandwidth": {}}

class SimpleTopo(Topo):
    def build(self):
        self.topology_data = {"distances": {}, "bandwidth": {}}
        
        positions = {
            make_dpid(1): {"lat": -23.5505, "lon": -46.6333},
            "10.0.0.2": {"lat": -23.5515, "lon": -46.6343},
            "10.0.0.3": {"lat": -23.5495, "lon": -46.6323}
        }
        
        h1 = self.addHost('h1', ip='10.0.0.2')
        h2 = self.addHost('h2', ip='10.0.0.3')
        s1 = self.addSwitch('s1', dpid=make_dpid(1), protocols='OpenFlow13')

        # Links with bandwidth and distance-based delay
        for host_ip, host in [("10.0.0.2", h1), ("10.0.0.3", h2)]:
            dist = haversine_distance(
                positions[host_ip]["lat"], positions[host_ip]["lon"],
                positions[make_dpid(1)]["lat"], positions[make_dpid(1)]["lon"]
            )
            delay = dist / PROPAGATION_SPEED_KM_PER_MS
            self.addLink(host, s1, bw=HOST_BW_MBPS, delay=f"{delay:.2f}ms")
            self.topology_data["bandwidth"][f"{host_ip}-{make_dpid(1)}"] = HOST_BW_MBPS
        
        # Calculate only direct connection distances
        switch_dpid = make_dpid(1)
        host_ips = ["10.0.0.2", "10.0.0.3"]
        
        # Host to switch distances (direct connections only)
        for host_ip in host_ips:
            dist = haversine_distance(
                positions[host_ip]["lat"], positions[host_ip]["lon"],
                positions[switch_dpid]["lat"], positions[switch_dpid]["lon"]
            )
            self.topology_data["distances"][f"{host_ip}-{switch_dpid}"] = dist
        
        # Host to host distances (same switch only)
        for host1_ip in host_ips:
            for host2_ip in host_ips:
                if host1_ip != host2_ip:
                    # Same switch - very small distance
                    self.topology_data["distances"][f"{host1_ip}-{host2_ip}"] = 0.1

    def get_topology_data(self, net):
        return self.topology_data

class Tower(Topo):
    def build(self, num_spines=2, num_leafs=4, hosts_per_leaf=5):
        self.topology_data = {"distances": {}, "bandwidth": {}}
        
        # Spine positions (base coordinates in Brazil)
        base_spine_positions = [
            {"lat": -23.5505, "lon": -46.6333},  # São Paulo
            {"lat": -22.9068, "lon": -43.1729},  # Rio de Janeiro  
            {"lat": -15.7801, "lon": -47.9292},  # Brasília
            {"lat": -19.9167, "lon": -43.9345},  # Belo Horizonte
            {"lat": -8.0476, "lon": -34.8770},   # Recife
            {"lat": -3.7319, "lon": -38.5267},   # Fortaleza
        ]
        
        # Leaf positions (distributed around spines)
        base_leaf_positions = [
            {"lat": -23.5320, "lon": -46.6414}, # São Paulo área
            {"lat": -23.5689, "lon": -46.6239}, # São Paulo área 
            {"lat": -22.9519, "lon": -43.2105}, # Rio área
            {"lat": -22.8305, "lon": -43.2192}, # Rio área
            {"lat": -15.7500, "lon": -47.8800}, # Brasília área
            {"lat": -15.8100, "lon": -48.0000}, # Brasília área
            {"lat": -19.8900, "lon": -43.9000}, # BH área
            {"lat": -19.9400, "lon": -43.9700}, # BH área
        ]
        
        # Generate dynamic positions
        dpid_positions = {}
        
        # Spine switches
        for i in range(num_spines):
            spine_dpid = make_dpid(i + 1)
            if i < len(base_spine_positions):
                dpid_positions[spine_dpid] = base_spine_positions[i]
            else:
                # Generate new positions around existing ones
                base_pos = base_spine_positions[i % len(base_spine_positions)]
                dpid_positions[spine_dpid] = {
                    "lat": base_pos["lat"] + random.uniform(-2, 2),
                    "lon": base_pos["lon"] + random.uniform(-2, 2)
                }
        
        # Leaf switches  
        for i in range(num_leafs):
            leaf_dpid = make_dpid(10 + i + 1)
            if i < len(base_leaf_positions):
                dpid_positions[leaf_dpid] = base_leaf_positions[i]
            else:
                # Generate positions near spines
                spine_idx = i % num_spines
                spine_dpid = make_dpid(spine_idx + 1)
                spine_pos = dpid_positions[spine_dpid]
                dpid_positions[leaf_dpid] = {
                    "lat": spine_pos["lat"] + random.uniform(-0.5, 0.5),
                    "lon": spine_pos["lon"] + random.uniform(-0.5, 0.5)
                }
        
        # Host positions
        host_positions = {}
        total_hosts = num_leafs * hosts_per_leaf
        
        for i in range(1, total_hosts + 1):
            leaf_idx = ((i-1) // hosts_per_leaf)
            leaf_dpid = make_dpid(10 + leaf_idx + 1)
            leaf_pos = dpid_positions[leaf_dpid]
            
            lat_offset = random.uniform(-0.01, 0.01) 
            lon_offset = random.uniform(-0.01, 0.01)
            
            # Gera IP válido usando múltiplas subnets (10.0.X.Y) - começa do .2
            subnet = (i - 1) // 253  # Subnet 0, 1, 2, ...
            host_num = ((i - 1) % 253) + 2  # Host 2-254 (evita .1)
            host_ip = f"10.0.{subnet}.{host_num}"
            
            host_positions[host_ip] = {
                "lat": leaf_pos["lat"] + lat_offset,
                "lon": leaf_pos["lon"] + lon_offset
            }
        
        all_positions = {**dpid_positions, **host_positions}
        
        # Build spines
        spines = []
        for i in range(num_spines):
            spine_name = f's{i+1}'
            spine_dpid = make_dpid(i + 1)
            spine = self.addSwitch(spine_name, dpid=spine_dpid, protocols="OpenFlow13")
            spines.append(spine)

        # Spine-to-spine links (full mesh)
        for i in range(num_spines):
            for j in range(i + 1, num_spines):
                spine1_dpid = make_dpid(i + 1)
                spine2_dpid = make_dpid(j + 1)
                
                dist = haversine_distance(
                    dpid_positions[spine1_dpid]["lat"], dpid_positions[spine1_dpid]["lon"],
                    dpid_positions[spine2_dpid]["lat"], dpid_positions[spine2_dpid]["lon"]
                )
                delay = dist / PROPAGATION_SPEED_KM_PER_MS
                
                self.addLink(spines[i], spines[j], 
                            bw=MIN_BACKBONE_BW_MBPS,
                            delay=f"{delay:.2f}ms",
                            loss=0.1,
                            max_queue_size=50,
                            use_htb=True)
                self.topology_data["bandwidth"][f"{spine1_dpid}-{spine2_dpid}"] = MIN_BACKBONE_BW_MBPS

        # Build leafs
        leafs = []
        for i in range(num_leafs):
            leaf_name = f'l{i+1}'
            leaf_dpid = make_dpid(10 + i + 1)
            leaf = self.addSwitch(leaf_name, dpid=leaf_dpid, protocols="OpenFlow13")
            leafs.append(leaf)

        # Leaf-spine links
        for i, leaf in enumerate(leafs):
            leaf_dpid = make_dpid(11 + i)
            for j, spine in enumerate(spines):
                spine_dpid = make_dpid(1 + j)
                
                leaf_spine_dist = haversine_distance(
                    dpid_positions[leaf_dpid]["lat"], dpid_positions[leaf_dpid]["lon"],
                    dpid_positions[spine_dpid]["lat"], dpid_positions[spine_dpid]["lon"]
                )
                leaf_spine_delay = leaf_spine_dist / PROPAGATION_SPEED_KM_PER_MS
                
                # Specific bottlenecks
                if (i == 0 and j == 0) or (i == 2 and j == 1):
                    link_bw_mbps = MIN_BACKBONE_BW_MBPS
                    queue_size = 50
                else:
                    link_bw_mbps = MAX_BACKBONE_BW_MBPS
                    queue_size = 100
                    
                self.addLink(leaf, spine,
                            bw=link_bw_mbps,
                            delay=f"{leaf_spine_delay:.2f}ms",
                            loss=0.1,
                            max_queue_size=queue_size,
                            use_htb=True)
                self.topology_data["bandwidth"][f"{leaf_dpid}-{spine_dpid}"] = link_bw_mbps

            # Host-leaf links
            for j in range(hosts_per_leaf):
                host_global_num = (i * hosts_per_leaf) + j + 1
                
                # Gera IP válido usando múltiplas subnets - começa do .2
                subnet = (host_global_num - 1) // 253
                host_num = ((host_global_num - 1) % 253) + 2
                host_ip = f'10.0.{subnet}.{host_num}'
                
                host = self.addHost(f'h{host_global_num}', ip=host_ip)
                print(host)
                
                host_leaf_dist = haversine_distance(
                    host_positions[host_ip]["lat"], host_positions[host_ip]["lon"],
                    dpid_positions[leaf_dpid]["lat"], dpid_positions[leaf_dpid]["lon"]
                )
                host_leaf_delay = host_leaf_dist / PROPAGATION_SPEED_KM_PER_MS
                
                self.addLink(host, leaf, 
                           bw=HOST_BW_MBPS, 
                           delay=f"{host_leaf_delay:.2f}ms")
                self.topology_data["bandwidth"][f"{host_ip}-{leaf_dpid}"] = HOST_BW_MBPS
        
        # Calculate only real connection distances
        
        # 1. Host to switch distances (direct connections)
        for i in range(1, total_hosts + 1):
            leaf_idx = ((i-1) // hosts_per_leaf)
            leaf_dpid = make_dpid(10 + leaf_idx + 1)
            subnet = (i - 1) // 253
            host_num = ((i - 1) % 253) + 2
            host_ip = f"10.0.{subnet}.{host_num}"
            
            # Host to its leaf switch
            host_leaf_dist = haversine_distance(
                host_positions[host_ip]["lat"], host_positions[host_ip]["lon"],
                dpid_positions[leaf_dpid]["lat"], dpid_positions[leaf_dpid]["lon"]
            )
            self.topology_data["distances"][f"{host_ip}-{leaf_dpid}"] = host_leaf_dist
        
        # 2. Switch to switch distances (only for connected switches)
        # Spine to spine connections
        for i in range(num_spines):
            for j in range(i + 1, num_spines):
                spine1_dpid = make_dpid(i + 1)
                spine2_dpid = make_dpid(j + 1)
                dist = haversine_distance(
                    dpid_positions[spine1_dpid]["lat"], dpid_positions[spine1_dpid]["lon"],
                    dpid_positions[spine2_dpid]["lat"], dpid_positions[spine2_dpid]["lon"]
                )
                self.topology_data["distances"][f"{spine1_dpid}-{spine2_dpid}"] = dist
        
        # Leaf to spine connections
        for i in range(num_leafs):
            leaf_dpid = make_dpid(11 + i)
            for j in range(num_spines):
                spine_dpid = make_dpid(1 + j)
                dist = haversine_distance(
                    dpid_positions[leaf_dpid]["lat"], dpid_positions[leaf_dpid]["lon"],
                    dpid_positions[spine_dpid]["lat"], dpid_positions[spine_dpid]["lon"]
                )
                self.topology_data["distances"][f"{leaf_dpid}-{spine_dpid}"] = dist
        
        # 3. Host to host distances (only same switch, avoid duplicates)
        for i in range(num_leafs):
            leaf_hosts = []
            start_host = i * hosts_per_leaf + 1
            end_host = start_host + hosts_per_leaf
            
            for h in range(start_host, end_host):
                if h <= total_hosts:
                    subnet = (h - 1) // 253
                    host_num = ((h - 1) % 253) + 2
                    host_ip = f"10.0.{subnet}.{host_num}"
                    leaf_hosts.append(host_ip)
            
            # Calculate distances between hosts on same switch (avoid duplicates)
            for j, host1_ip in enumerate(leaf_hosts):
                for k, host2_ip in enumerate(leaf_hosts):
                    if j < k:  # Only add one direction to avoid duplicates
                        self.topology_data["distances"][f"{host1_ip}-{host2_ip}"] = 0.1

    def get_topology_data(self, net):
        return self.topology_data

class GmlTopo(Topo):
    """Mininet topology from GML file"""
    def build(self, gml_file):
        self.topology_data = {"distances": {}, "bandwidth": {}}
        
        if not os.path.exists(gml_file):
            raise FileNotFoundError(f"GML file '{gml_file}' not found.")
        
        G = nx.read_gml(gml_file, label='id')
        
        switch_nodes = [n for n, d in G.nodes(data=True) if 'Internal' not in d.get('label', '')][:100]
        backbone_nodes = [n for n, d in G.nodes(data=True) if d.get('label', '').startswith('backbone')]
        edge_nodes = [n for n in switch_nodes if n not in backbone_nodes][:50]
        
        switches = {}
        for i, node in enumerate(switch_nodes):
            switch_name = f's{i+1}'
            switch_dpid = make_dpid(i + 1)
            switches[node] = {
                'name': switch_name,
                'dpid': switch_dpid,
                'mininet_obj': self.addSwitch(switch_name, dpid=switch_dpid, protocols="OpenFlow13")
            }
        
        # Add switch-to-switch links
        for src, dst in G.edges():
            if src in switches and dst in switches:
                src_dpid = switches[src]['dpid']
                dst_dpid = switches[dst]['dpid']
                
                bw = random.uniform(MIN_BACKBONE_BW_MBPS, MAX_BACKBONE_BW_MBPS)
                delay = random.uniform(1, 20)
                
                self.addLink(
                    switches[src]['mininet_obj'], 
                    switches[dst]['mininet_obj'],
                    bw=bw, 
                    delay=f"{delay:.2f}ms",
                    loss=0.1,
                    use_htb=True
                )
                
                self.topology_data["bandwidth"][f"{src_dpid}-{dst_dpid}"] = bw
        
        # Get node positions
        node_positions = {}
        for node, data in G.nodes(data=True):
            if 'Longitude' in data and 'Latitude' in data:
                try:
                    lon = float(data['Longitude'])
                    lat = float(data['Latitude'])
                    node_positions[node] = {"lat": lat, "lon": lon}
                except ValueError:
                    continue
        
        # Generate circular positions if no geographic data
        if not node_positions:
            for i, node in enumerate(G.nodes()):
                angle = 2 * math.pi * i / len(G.nodes())
                lat = -15.0 + 10 * math.cos(angle)
                lon = -47.0 + 10 * math.sin(angle)
                node_positions[node] = {"lat": lat, "lon": lon}
        
        # Add hosts to edge switches
        edge_switches = [(node, switches[node]) for node in edge_nodes if node in switches][:MIN_HOSTS_PER_EDGE_SWITCH * 10]
        
        host_counter = 1
        host_to_switch_mapping = {}  # Track which host belongs to which switch
        
        for node, switch_info in edge_switches:
            num_hosts = random.randint(MIN_HOSTS_PER_EDGE_SWITCH, MAX_HOSTS_PER_EDGE_SWITCH)
            for _ in range(num_hosts):
                subnet = (host_counter - 1) // 253
                host_num = ((host_counter - 1) % 253) + 2
                host_ip = f"10.0.{subnet}.{host_num}"
                
                host_name = f'h{host_counter}'
                host = self.addHost(host_name, ip=host_ip)
                
                self.addLink(host, switch_info['mininet_obj'], 
                            bw=HOST_BW_MBPS,
                            delay="0.1ms",
                            use_htb=True)
                
                # Store host-switch mapping
                host_to_switch_mapping[host_ip] = switch_info['dpid']
                
                # Add bandwidth data
                self.topology_data["bandwidth"][f"{host_ip}-{switch_info['dpid']}"] = HOST_BW_MBPS
                
                # Add host-switch distance (very small since host is directly connected)
                self.topology_data["distances"][f"{host_ip}-{switch_info['dpid']}"] = 0.1
                
                host_counter += 1
        
        # Calculate distances between switches
        for src_node in switch_nodes:
            if src_node in switches and src_node in node_positions:
                src_dpid = switches[src_node]['dpid']
                for dst_node in switch_nodes:
                    if dst_node in switches and dst_node in node_positions and src_node != dst_node:
                        dst_dpid = switches[dst_node]['dpid']
                        pos1, pos2 = node_positions[src_node], node_positions[dst_node]
                        dist = haversine_distance(pos1["lat"], pos1["lon"], pos2["lat"], pos2["lon"])
                        self.topology_data["distances"][f"{src_dpid}-{dst_dpid}"] = dist
        
        # Calculate distances between hosts (only same switch)
        # Group hosts by switch
        switch_to_hosts = {}
        for host_ip, switch_dpid in host_to_switch_mapping.items():
            if switch_dpid not in switch_to_hosts:
                switch_to_hosts[switch_dpid] = []
            switch_to_hosts[switch_dpid].append(host_ip)
        
        # Only add distances between hosts on the same switch
        for switch_dpid, host_list in switch_to_hosts.items():
            for host1_ip in host_list:
                for host2_ip in host_list:
                    if host1_ip != host2_ip:
                        self.topology_data["distances"][f"{host1_ip}-{host2_ip}"] = 0.1

    def get_topology_data(self, net):
        return self.topology_data

def run(topo):
    setLogLevel('info')

    net = Mininet(topo=topo, build=False, controller=None, ipBase='10.0.0.0/8', link=TCLink)
    controllers = os.getenv('CONTROLERS', '172.17.0.2').split(',')

    for i, ip in enumerate(controllers):
        name = f"c{i}"
        c = RemoteController(name, ip=ip, port=6653)
        net.addController(c)

    net.build()
    net.start()
    sleep(2)

    for host in net.hosts:
        host.lock = Lock()
        host.cmd("ping -c 1 10.0.0.1 &")

    topology_data = generate_network_topology_data(topo, net)
    
    json_filename = "topology_data.json"
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), json_filename)
    
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(topology_data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    return net

if __name__ == '__main__':
    setLogLevel('info')
    net = run(Tower())
    info("*** Starting CLI...\n")
    CLI(net)
    info("*** Stopping network...\n")
    net.stop()