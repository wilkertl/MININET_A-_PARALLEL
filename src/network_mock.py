import os
import math
import random
import json
from time import sleep
from dotenv import load_dotenv

load_dotenv()
random.seed(42)

# Network configuration constants
MIN_BACKBONE_BW_MBPS = 30.0  
MAX_BACKBONE_BW_MBPS = 100.0  
PROPAGATION_SPEED_KM_PER_MS = 200  
MIN_HOSTS_PER_EDGE_SWITCH = 2
MAX_HOSTS_PER_EDGE_SWITCH = 4
EDGE_SWITCH_DEGREE_THRESHOLD = 2  
LOW_LINK_CHANCE = 0.30 
HOST_BW_MBPS = 10.0

def make_dpid(index):
    """Generate a 16-digit hexadecimal formatted DPID"""
    return format(index, '016x')

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate geodesic distance in km"""
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

class MockHost:
    """Mock host object to simulate Mininet host"""
    def __init__(self, name, ip):
        self.name = name
        self.IP = ip
        self.connected_switches = []
    
    def cmd(self, command):
        """Mock command execution"""
        return f"Mock execution of: {command}"

class MockSwitch:
    """Mock switch object to simulate Mininet switch"""
    def __init__(self, name, dpid):
        self.name = name
        self.dpid = dpid
        self.connected_hosts = []
        self.connected_switches = []

class MockController:
    """Mock controller object"""
    def __init__(self, name, ip, port):
        self.name = name
        self.ip = ip
        self.port = port

class MockNetwork:
    """Mock network object to simulate Mininet network"""
    def __init__(self, topo):
        self.topo = topo
        self.hosts = []
        self.switches = []
        self.controllers = []
        self.links = []
        self.running = False
    
    def addController(self, controller):
        self.controllers.append(controller)
    
    def build(self):
        """Mock build process"""
        print("Mock: Building network...")
        # Simulate topology building
        if hasattr(self.topo, 'mock_hosts'):
            self.hosts = self.topo.mock_hosts
        if hasattr(self.topo, 'mock_switches'):
            self.switches = self.topo.mock_switches
        if hasattr(self.topo, 'mock_links'):
            self.links = self.topo.mock_links
    
    def start(self):
        """Mock start process"""
        print("Mock: Starting network...")
        self.running = True
    
    def stop(self):
        """Mock stop process"""
        print("Mock: Stopping network...")
        self.running = False

class MockTopo:
    """Base mock topology class"""
    def __init__(self):
        self.mock_hosts = []
        self.mock_switches = []
        self.mock_links = []
        self.topology_data = {"distances": {}, "bandwidth": {}}
    
    def addHost(self, name, ip=None):
        host = MockHost(name, ip)
        self.mock_hosts.append(host)
        return host
    
    def addSwitch(self, name, dpid=None, protocols=None):
        switch = MockSwitch(name, dpid)
        self.mock_switches.append(switch)
        return switch
    
    def addLink(self, node1, node2, **params):
        link = {
            'node1': node1,
            'node2': node2,
            'params': params
        }
        self.mock_links.append(link)
        return link

class SimpleTopo(MockTopo):
    def build(self):
        super().__init__()
        self.topology_data = {"distances": {}, "bandwidth": {}}
        
        positions = {
            make_dpid(1): {"lat": -23.5505, "lon": -46.6333},
            "10.0.0.2": {"lat": -23.5515, "lon": -46.6343},
            "10.0.0.3": {"lat": -23.5495, "lon": -46.6323}
        }
        
        h1 = self.addHost('h1', ip='10.0.0.2')
        h2 = self.addHost('h2', ip='10.0.0.3')
        s1 = self.addSwitch('s1', dpid=make_dpid(1), protocols='OpenFlow13')

        for host_ip, host in [("10.0.0.2", h1), ("10.0.0.3", h2)]:
            dist = haversine_distance(
                positions[host_ip]["lat"], positions[host_ip]["lon"],
                positions[make_dpid(1)]["lat"], positions[make_dpid(1)]["lon"]
            )
            delay = dist / PROPAGATION_SPEED_KM_PER_MS
            self.addLink(host, s1, bw=HOST_BW_MBPS, delay=f"{delay:.2f}ms")
            self.topology_data["bandwidth"][f"{host_ip}-{make_dpid(1)}"] = HOST_BW_MBPS
        
        switch_dpid = make_dpid(1)
        host_ips = ["10.0.0.2", "10.0.0.3"]
        
        for host_ip in host_ips:
            dist = haversine_distance(
                positions[host_ip]["lat"], positions[host_ip]["lon"],
                positions[switch_dpid]["lat"], positions[switch_dpid]["lon"]
            )
            self.topology_data["distances"][f"{host_ip}-{switch_dpid}"] = dist
        
        for host1_ip in host_ips:
            for host2_ip in host_ips:
                if host1_ip != host2_ip:
                    self.topology_data["distances"][f"{host1_ip}-{host2_ip}"] = 0.1

    def get_topology_data(self, net):
        return self.topology_data

class Tower(MockTopo):
    def build(self, num_spines=2, num_leafs=4, hosts_per_leaf=5):
        super().__init__()
        self.topology_data = {"distances": {}, "bandwidth": {}}
        
        base_spine_positions = [
            {"lat": -23.5505, "lon": -46.6333},
            {"lat": -22.9068, "lon": -43.1729},
            {"lat": -15.7801, "lon": -47.9292},
            {"lat": -19.9167, "lon": -43.9345},
            {"lat": -8.0476, "lon": -34.8770},
            {"lat": -3.7319, "lon": -38.5267},
        ]
        
        base_leaf_positions = [
            {"lat": -23.5320, "lon": -46.6414},
            {"lat": -23.5689, "lon": -46.6239},
            {"lat": -22.9519, "lon": -43.2105},
            {"lat": -22.8305, "lon": -43.2192},
            {"lat": -15.7500, "lon": -47.8800},
            {"lat": -15.8100, "lon": -48.0000},
            {"lat": -19.8900, "lon": -43.9000},
            {"lat": -19.9400, "lon": -43.9700},
        ]
        
        dpid_positions = {}
        spines = []
        for i in range(num_spines):
            spine_dpid = make_dpid(i + 1)
            if i < len(base_spine_positions):
                dpid_positions[spine_dpid] = base_spine_positions[i]
            else:
                base_pos = base_spine_positions[i % len(base_spine_positions)]
                dpid_positions[spine_dpid] = {
                    "lat": base_pos["lat"] + random.uniform(-2, 2),
                    "lon": base_pos["lon"] + random.uniform(-2, 2)
                }
            
            spine_name = f's{i+1}'
            spine = self.addSwitch(spine_name, dpid=spine_dpid, protocols="OpenFlow13")
            spines.append(spine)
        
        # Create leaf switches
        leafs = []
        for i in range(num_leafs):
            leaf_dpid = make_dpid(10 + i + 1)
            if i < len(base_leaf_positions):
                dpid_positions[leaf_dpid] = base_leaf_positions[i]
            else:
                spine_idx = i % num_spines
                spine_dpid = make_dpid(spine_idx + 1)
                spine_pos = dpid_positions[spine_dpid]
                dpid_positions[leaf_dpid] = {
                    "lat": spine_pos["lat"] + random.uniform(-0.5, 0.5),
                    "lon": spine_pos["lon"] + random.uniform(-0.5, 0.5)
                }
            
            leaf_name = f'l{i+1}'
            leaf = self.addSwitch(leaf_name, dpid=leaf_dpid, protocols="OpenFlow13")
            leafs.append(leaf)
        
        # Create hosts
        host_positions = {}
        total_hosts = num_leafs * hosts_per_leaf
        
        for i in range(1, total_hosts + 1):
            leaf_idx = ((i-1) // hosts_per_leaf)
            leaf_dpid = make_dpid(10 + leaf_idx + 1)
            leaf_pos = dpid_positions[leaf_dpid]
            
            lat_offset = random.uniform(-0.01, 0.01) 
            lon_offset = random.uniform(-0.01, 0.01)
            
            subnet = (i - 1) // 253
            host_num = ((i - 1) % 253) + 2
            host_ip = f"10.0.{subnet}.{host_num}"
            
            host_positions[host_ip] = {
                "lat": leaf_pos["lat"] + lat_offset,
                "lon": leaf_pos["lon"] + lon_offset
            }
            
            host = self.addHost(f'h{i}', ip=host_ip)
            
            # Connect host to leaf
            leaf = leafs[leaf_idx]
            host_leaf_dist = haversine_distance(
                host_positions[host_ip]["lat"], host_positions[host_ip]["lon"],
                dpid_positions[leaf_dpid]["lat"], dpid_positions[leaf_dpid]["lon"]
            )
            host_leaf_delay = host_leaf_dist / PROPAGATION_SPEED_KM_PER_MS
            
            self.addLink(host, leaf, 
                       bw=HOST_BW_MBPS, 
                       delay=f"{host_leaf_delay:.2f}ms")
            self.topology_data["bandwidth"][f"{host_ip}-{leaf_dpid}"] = HOST_BW_MBPS
            self.topology_data["distances"][f"{host_ip}-{leaf_dpid}"] = host_leaf_dist

        # Connect spines to each other
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
                self.topology_data["distances"][f"{spine1_dpid}-{spine2_dpid}"] = dist

        for i, leaf in enumerate(leafs):
            leaf_dpid = make_dpid(11 + i)
            for j, spine in enumerate(spines):
                spine_dpid = make_dpid(1 + j)
                
                leaf_spine_dist = haversine_distance(
                    dpid_positions[leaf_dpid]["lat"], dpid_positions[leaf_dpid]["lon"],
                    dpid_positions[spine_dpid]["lat"], dpid_positions[spine_dpid]["lon"]
                )
                leaf_spine_delay = leaf_spine_dist / PROPAGATION_SPEED_KM_PER_MS
                
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
                self.topology_data["distances"][f"{leaf_dpid}-{spine_dpid}"] = leaf_spine_dist

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
            
            for j, host1_ip in enumerate(leaf_hosts):
                for k, host2_ip in enumerate(leaf_hosts):
                    if j < k:
                        self.topology_data["distances"][f"{host1_ip}-{host2_ip}"] = 0.1

    def get_topology_data(self, net):
        return self.topology_data

class GmlTopo(MockTopo):
    """Mock GML topology generating realistic network structure"""
    def build(self, gml_file=None):
        super().__init__()
        self.topology_data = {"distances": {}, "bandwidth": {}}
        
        num_switches = 20
        switches = {}
        
        for i in range(num_switches):
            switch_name = f's{i+1}'
            switch_dpid = make_dpid(i + 1)
            switch = self.addSwitch(switch_name, dpid=switch_dpid, protocols="OpenFlow13")
            switches[i] = {
                'name': switch_name,
                'dpid': switch_dpid,
                'mininet_obj': switch
            }
        
        for i in range(num_switches):
            for j in range(i + 1, min(i + 4, num_switches)):
                src_dpid = switches[i]['dpid']
                dst_dpid = switches[j]['dpid']
                
                bw = random.uniform(MIN_BACKBONE_BW_MBPS, MAX_BACKBONE_BW_MBPS)
                delay = random.uniform(1, 20)
                
                self.addLink(
                    switches[i]['mininet_obj'], 
                    switches[j]['mininet_obj'],
                    bw=bw, 
                    delay=f"{delay:.2f}ms",
                    loss=0.1,
                    use_htb=True
                )
                
                self.topology_data["bandwidth"][f"{src_dpid}-{dst_dpid}"] = bw
        
        node_positions = {}
        for i in range(num_switches):
            angle = 2 * math.pi * i / num_switches
            lat = -15.0 + 5 * math.cos(angle)
            lon = -47.0 + 5 * math.sin(angle)
            node_positions[i] = {"lat": lat, "lon": lon}
        
        edge_switches = list(range(min(10, num_switches)))
        host_counter = 1
        
        for switch_idx in edge_switches:
            switch_info = switches[switch_idx]
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
                
                self.topology_data["bandwidth"][f"{host_ip}-{switch_info['dpid']}"] = HOST_BW_MBPS
                self.topology_data["distances"][f"{host_ip}-{switch_info['dpid']}"] = 0.1
                
                host_counter += 1
        
        for i in range(num_switches):
            src_dpid = switches[i]['dpid']
            for j in range(i + 1, num_switches):
                dst_dpid = switches[j]['dpid']
                pos1, pos2 = node_positions[i], node_positions[j]
                dist = haversine_distance(pos1["lat"], pos1["lon"], pos2["lat"], pos2["lon"])
                self.topology_data["distances"][f"{src_dpid}-{dst_dpid}"] = dist

    def get_topology_data(self, net):
        return self.topology_data

def generate_network_topology_data(topo, net):
    """Generate simplified topology data for JSON file"""
    if hasattr(topo, 'get_topology_data'):
        return topo.get_topology_data(net)
    else:
        return {"distances": {}, "bandwidth": {}}

def run(topo):
    print("Mock: Setting up network...")

    net = MockNetwork(topo)
    
    controllers = os.getenv('CONTROLERS', '172.17.0.2').split(',')
    for i, ip in enumerate(controllers):
        name = f"c{i}"
        c = MockController(name, ip, 6653)
        net.addController(c)

    net.build()
    net.start()

    print(f"Mock: Network running with {len(net.hosts)} hosts and {len(net.switches)} switches")

    topology_data = generate_network_topology_data(topo, net)
    
    json_filename = "topology_data_mock.json"
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), json_filename)
    
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(topology_data, f, indent=2, ensure_ascii=False)
        print(f"Mock: Topology data saved to {json_path}")
    except Exception as e:
        print(f"Mock: Error saving topology data: {e}")

    return net

def info(msg):
    """Mock info function"""
    print(f"Mock Info: {msg}")

def setLogLevel(level):
    """Mock log level setter"""
    print(f"Mock: Log level set to {level}")

class CLI:
    """Mock CLI class"""
    def __init__(self, net):
        self.net = net
        print("Mock CLI: Network ready for testing")
        print(f"Mock CLI: Available hosts: {[h.name for h in net.hosts]}")
        print(f"Mock CLI: Available switches: {[s.name for s in net.switches]}")
        print("Mock CLI: Use this network object for routing algorithm tests")

if __name__ == '__main__':
    print("Mock Network: Starting...")
    net = run(Tower())
    info("*** Starting Mock CLI...")
    CLI(net)
    info("*** Stopping mock network...")
    net.stop() 