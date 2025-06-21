import os
import sys
import math
import random
import networkx as nx
import json
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info, error
from time import sleep
from dotenv import load_dotenv
from threading import Lock

load_dotenv()

random.seed(42)

# Configurações para topologia GML
MIN_BACKBONE_BW_MBPS = 30.0  
MAX_BACKBONE_BW_MBPS = 100.0  
PROPAGATION_SPEED_KM_PER_MS = 200  
MIN_HOSTS_PER_EDGE_SWITCH = 1
MAX_HOSTS_PER_EDGE_SWITCH = 7
EDGE_SWITCH_DEGREE_THRESHOLD = 2  
LOW_LINK_CHANCE = 0.30 
HOST_BW_MBPS = 10.0

# Configurações para experimento de sobrecarga Tower
SPINE_BOTTLENECK_BW_MBPS = 30.0   # Gargalo intencional nos spines
LEAF_SPINE_BW_MBPS = 50.0         # Links leaf-spine normais
OVERLOAD_LINK_CHANCE = 0.3        # 30% chance de link ser gargalo

def make_dpid(index):
    """Gera um DPID formatado com 16 dígitos hexadecimais"""
    return format(index, '016x')

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calcula a distancia geodesica em km."""
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def generate_network_topology_data(topo, net):
    """
    Gera dados simplificados da topologia para arquivo JSON
    Inclui apenas distâncias e bandwidth dos links
    """
    # Chama o método da topologia específica
    if hasattr(topo, 'get_topology_data'):
        return topo.get_topology_data(net)
    else:
        # Fallback para topologias que não implementaram o método
        return {"distances": {}, "bandwidth": {}}

class SimpleTopo(Topo):
    def build(self):
        # Inicializa dados da topologia
        self.topology_data = {"distances": {}, "bandwidth": {}}
        
        # Posições para cálculo de distâncias (usando DPIDs e IPs)
        positions = {
            make_dpid(1): {"lat": -23.5505, "lon": -46.6333},  # s1 -> DPID
            "10.0.0.1": {"lat": -23.5515, "lon": -46.6343},   # h1 -> IP
            "10.0.0.2": {"lat": -23.5495, "lon": -46.6323}    # h2 -> IP
        }
        
        # Constrói a rede
        h1 = self.addHost('h1', ip='10.0.0.1')
        h2 = self.addHost('h2', ip='10.0.0.2')
        s1 = self.addSwitch('s1', dpid=make_dpid(1), protocols='OpenFlow13')

        # Adiciona links COM bandwidth e delay baseado na distância
        # Link h1-s1
        h1_s1_dist = haversine_distance(
            positions["10.0.0.1"]["lat"], positions["10.0.0.1"]["lon"],
            positions[make_dpid(1)]["lat"], positions[make_dpid(1)]["lon"]
        )
        h1_s1_delay = h1_s1_dist / PROPAGATION_SPEED_KM_PER_MS
        self.addLink(h1, s1, bw=HOST_BW_MBPS, delay=f"{h1_s1_delay:.2f}ms")
        self.topology_data["bandwidth"][f"10.0.0.1-{make_dpid(1)}"] = HOST_BW_MBPS
        
        # Link h2-s1
        h2_s1_dist = haversine_distance(
            positions["10.0.0.2"]["lat"], positions["10.0.0.2"]["lon"],
            positions[make_dpid(1)]["lat"], positions[make_dpid(1)]["lon"]
        )
        h2_s1_delay = h2_s1_dist / PROPAGATION_SPEED_KM_PER_MS
        self.addLink(h2, s1, bw=HOST_BW_MBPS, delay=f"{h2_s1_delay:.2f}ms")
        self.topology_data["bandwidth"][f"10.0.0.2-{make_dpid(1)}"] = HOST_BW_MBPS
        
        # Calcula e armazena distâncias usando DPIDs e IPs
        nodes = ["10.0.0.1", "10.0.0.2", make_dpid(1)]
        for i, node1 in enumerate(nodes):
            for j, node2 in enumerate(nodes):
                if i != j:
                    pos1, pos2 = positions[node1], positions[node2]
                    dist = haversine_distance(pos1["lat"], pos1["lon"], pos2["lat"], pos2["lon"])
                    self.topology_data["distances"][f"{node1}-{node2}"] = dist

    def get_topology_data(self, net):
        """Retorna os dados armazenados durante o build()"""
        return self.topology_data

class Tower( Topo ):
    def build( self ):
        # Inicializa dados da topologia
        self.topology_data = {"distances": {}, "bandwidth": {}}
        
        # Mapeamento DPID para posições
        dpid_positions = {
            # Spines (core) - DPIDs
            make_dpid(1): {"lat": -23.5505, "lon": -46.6333},  # s1
            make_dpid(2): {"lat": -22.9068, "lon": -43.1729},  # s2
            
            # Leafs (distribuídos geograficamente) - DPIDs  
            make_dpid(11): {"lat": -23.5320, "lon": -46.6414},  # l1
            make_dpid(12): {"lat": -23.5689, "lon": -46.6239},  # l2
            make_dpid(13): {"lat": -22.9519, "lon": -43.2105},  # l3
            make_dpid(14): {"lat": -22.8305, "lon": -43.2192},  # l4
        }
        
        # Posições dos hosts (baseadas em IPs)
        host_positions = {}
        for i in range(1, 21):  # 20 hosts
            leaf_idx = ((i-1) // 5) + 1  # 5 hosts por leaf
            leaf_dpid = make_dpid(10 + leaf_idx)  # 11, 12, 13, 14
            leaf_pos = dpid_positions[leaf_dpid]
            
            # Adiciona pequena variação à posição do leaf
            lat_offset = random.uniform(-0.01, 0.01) 
            lon_offset = random.uniform(-0.01, 0.01)
            
            host_ip = f"10.0.0.{i}"
            host_positions[host_ip] = {
                "lat": leaf_pos["lat"] + lat_offset,
                "lon": leaf_pos["lon"] + lon_offset
            }
        
        # Combina todas as posições
        all_positions = {**dpid_positions, **host_positions}
        
        # Constrói spines
        spines = [
            self.addSwitch('s1', dpid=make_dpid(1), protocols="OpenFlow13"),
            self.addSwitch('s2', dpid=make_dpid(2), protocols="OpenFlow13")
        ]

        # Link entre spines COM delay baseado na distância
        spine_bw_mbps = SPINE_BOTTLENECK_BW_MBPS
        s1_s2_dist = haversine_distance(
            dpid_positions[make_dpid(1)]["lat"], dpid_positions[make_dpid(1)]["lon"],
            dpid_positions[make_dpid(2)]["lat"], dpid_positions[make_dpid(2)]["lon"]
        )
        s1_s2_delay = s1_s2_dist / PROPAGATION_SPEED_KM_PER_MS
        print(f"INFO: Link spine {make_dpid(1)}-{make_dpid(2)} com {spine_bw_mbps}Mbps, {s1_s2_delay:.2f}ms delay (GARGALO)")
        self.addLink(spines[0], spines[1], 
                    bw=spine_bw_mbps,
                    delay=f"{s1_s2_delay:.2f}ms",
                    loss=0.1,
                    max_queue_size=50,
                    use_htb=True)
        # Armazena bandwidth do link spine-spine usando DPIDs
        self.topology_data["bandwidth"][f"{make_dpid(1)}-{make_dpid(2)}"] = spine_bw_mbps

        # Constrói leafs
        leafs = []
        for i in range(4):
            leaf = self.addSwitch(f'l{i+1}', dpid=make_dpid(11 + i), protocols="OpenFlow13")
            leafs.append(leaf)

        # Links leaf-spine COM delay baseado na distância
        for i, leaf in enumerate(leafs):
            leaf_dpid = make_dpid(11 + i)
            for j, spine in enumerate(spines):
                spine_dpid = make_dpid(1 + j)
                
                # Calcula distância e delay
                leaf_spine_dist = haversine_distance(
                    dpid_positions[leaf_dpid]["lat"], dpid_positions[leaf_dpid]["lon"],
                    dpid_positions[spine_dpid]["lat"], dpid_positions[spine_dpid]["lon"]
                )
                leaf_spine_delay = leaf_spine_dist / PROPAGATION_SPEED_KM_PER_MS
                
                # Cria gargalos em alguns links específicos
                if (i == 0 and j == 0) or (i == 2 and j == 1):  # l1-s1 e l3-s2 são gargalos
                    link_bw_mbps = SPINE_BOTTLENECK_BW_MBPS
                    queue_size = 50
                    print(f"INFO: Link {leaf_dpid}-{spine_dpid} com {link_bw_mbps}Mbps, {leaf_spine_delay:.2f}ms delay (GARGALO)")
                else:
                    link_bw_mbps = LEAF_SPINE_BW_MBPS
                    queue_size = 100
                    
                self.addLink(leaf, spine,
                            bw=link_bw_mbps,
                            delay=f"{leaf_spine_delay:.2f}ms",
                            loss=0.1,
                            max_queue_size=queue_size,
                            use_htb=True)
                # Armazena bandwidth do link usando DPIDs
                self.topology_data["bandwidth"][f"{leaf_dpid}-{spine_dpid}"] = link_bw_mbps

            # Links host-leaf COM delay baseado na distância
            for j in range(1, 6):
                host_num = j + i * 5
                host_ip = f'10.0.0.{host_num}'
                host = self.addHost(f'h{host_num}', ip=host_ip)
                
                # Calcula distância e delay host-leaf (muito pequeno)
                host_leaf_dist = haversine_distance(
                    host_positions[host_ip]["lat"], host_positions[host_ip]["lon"],
                    dpid_positions[leaf_dpid]["lat"], dpid_positions[leaf_dpid]["lon"]
                )
                host_leaf_delay = host_leaf_dist / PROPAGATION_SPEED_KM_PER_MS
                
                self.addLink(host, leaf, 
                           bw=HOST_BW_MBPS, 
                           delay=f"{host_leaf_delay:.2f}ms")
                # Armazena bandwidth do link host-leaf usando IP e DPID
                self.topology_data["bandwidth"][f"{host_ip}-{leaf_dpid}"] = HOST_BW_MBPS
        
        # Calcula e armazena todas as distâncias usando DPIDs e IPs
        all_nodes = list(all_positions.keys())
        for node1 in all_nodes:
            for node2 in all_nodes:
                if node1 != node2:
                    pos1, pos2 = all_positions[node1], all_positions[node2]
                    dist = haversine_distance(pos1["lat"], pos1["lon"], pos2["lat"], pos2["lon"])
                    self.topology_data["distances"][f"{node1}-{node2}"] = dist

    def get_topology_data(self, net):
        """Retorna os dados armazenados durante o build()"""
        return self.topology_data

class GmlTopo(Topo):
    """
    Classe de topologia do Mininet que constroi a rede
    a partir de um arquivo GML local.
    """
    def build(self, gml_file):
        # Inicializa dados da topologia
        self.topology_data = {"distances": {}, "bandwidth": {}}
        
        info("*** Lendo topologia do arquivo: {}\n".format(gml_file))
        G = None
        try:
            G = nx.read_gml(gml_file, label='id')
        except Exception:
            G = nx.read_gml(gml_file, label='label')

        # Salva o grafo para usar na geração de dados
        self.graph = G

        info("*** Adicionando switches...\n")
        switches = {}
        self.edge_switches = []
        self.backbone_switches = []
        # Mapeamento consistente: node_id -> dpid
        self.node_to_dpid = {}
        
        for idx, (node_id, node_data) in enumerate(G.nodes(data=True)):
            switch_name = str(node_id)
            dpid = make_dpid(idx + 1)
            switch_ref = self.addSwitch(switch_name, dpid=dpid, protocols='OpenFlow13')
            switches[node_id] = switch_ref
            self.node_to_dpid[node_id] = dpid  # Armazena mapeamento

        info("*** Classificando switches...\n")
        for node_id, switch_ref in switches.items():
            switch_degree = G.degree(node_id)
            switch_name = switch_ref if isinstance(switch_ref, str) else str(switch_ref)
            
            if switch_degree <= EDGE_SWITCH_DEGREE_THRESHOLD:
                self.edge_switches.append({
                    'id': node_id,
                    'name': switch_name,
                    'degree': switch_degree
                })
            else:
                self.backbone_switches.append({
                    'id': node_id,
                    'name': switch_name,
                    'degree': switch_degree
                })
        
        # Adiciona links entre switches E armazena bandwidth
        info("*** Adicionando links entre switches...\n")
        for u, v, edge_data in G.edges(data=True):
            switch_u = switches[u]
            switch_v = switches[v]
            u_dpid = self.node_to_dpid[u]
            v_dpid = self.node_to_dpid[v]
            
            # Usa distância do GML se disponível, senão calcula
            distance_km = edge_data['dist']
            delay_ms = distance_km / PROPAGATION_SPEED_KM_PER_MS
            
            # Atribui largura de banda baseada no grau dos nós
            bw_mbps = MAX_BACKBONE_BW_MBPS
            if random.uniform(0, 1) < LOW_LINK_CHANCE:
                bw_mbps = MIN_BACKBONE_BW_MBPS
            
            self.addLink(switch_u, switch_v, 
                        bw=bw_mbps,
                        delay=f"{delay_ms:.2f}ms",
                        loss=0.1,
                        max_queue_size=100,
                        use_htb=True)
            # Armazena bandwidth do link usando DPIDs
            self.topology_data["bandwidth"][f"{u_dpid}-{v_dpid}"] = bw_mbps
        
        # Adiciona hosts aos edge switches E armazena bandwidth
        info("*** Adicionando hosts aos edge switches...\n")
        for edge_switch_info in self.edge_switches:
            switch_name = edge_switch_info['name']
            switch_dpid = self.node_to_dpid[edge_switch_info['id']]
            switch_ref = switches[edge_switch_info['id']]
            num_hosts = random.randint(MIN_HOSTS_PER_EDGE_SWITCH, MAX_HOSTS_PER_EDGE_SWITCH)
            
            for j in range(num_hosts):
                # Gera IP baseado no switch e index do host
                host_ip = f"10.0.{abs(hash(switch_name)) % 250}.{j+1}"
                host_name = f'h{switch_name}_{j+1}'
                host = self.addHost(host_name, ip=host_ip)
                self.addLink(host, switch_ref, 
                           bw=HOST_BW_MBPS,
                           delay="0.1ms")  # Delay local pequeno
                # Armazena bandwidth do link host-switch usando IP e DPID
                self.topology_data["bandwidth"][f"{host_ip}-{switch_dpid}"] = HOST_BW_MBPS
        
        # Primeiro, adiciona distâncias dos edges do GML (mais precisas) usando DPIDs
        for u, v, edge_data in G.edges(data=True):
            u_dpid = self.node_to_dpid[u]
            v_dpid = self.node_to_dpid[v]
            distance_km = edge_data['dist']
            self.topology_data["distances"][f"{u_dpid}-{v_dpid}"] = distance_km
            self.topology_data["distances"][f"{v_dpid}-{u_dpid}"] = distance_km  # Bidirecional
        
        # Calcula e armazena distâncias baseadas nas posições GML usando DPIDs
        switch_positions = {}
        for node_id, node_data in G.nodes(data=True):
            if 'lat' in node_data and 'lon' in node_data:
                node_dpid = self.node_to_dpid[node_id]
                switch_positions[node_dpid] = {
                    "lat": node_data['lat'],
                    "lon": node_data['lon']
                }
        
        # Para pares de nós sem edge direto, calcula pela coordenadas
        for node1 in switch_positions:
            for node2 in switch_positions:
                if node1 != node2:
                    # Só calcula se não tiver sido definido pelos edges
                    if f"{node1}-{node2}" not in self.topology_data["distances"]:
                        pos1, pos2 = switch_positions[node1], switch_positions[node2]
                        dist = haversine_distance(pos1["lat"], pos1["lon"], pos2["lat"], pos2["lon"])
                        self.topology_data["distances"][f"{node1}-{node2}"] = dist

    def get_topology_data(self, net):
        """Retorna os dados armazenados durante o build()"""
        return self.topology_data

def run(topo):
    setLogLevel('info')

    net = Mininet(topo=topo, build=False, controller=None, ipBase='10.0.0.0/8', link=TCLink)
    controllers = os.getenv('CONTROLERS', '172.17.0.2').split(',')

    for i, ip in enumerate(controllers):
        name = "c{}".format(i)
        c = RemoteController(name, ip=ip, port=6653)
        net.addController(c)

    net.build()
    net.start()

    sleep(2)

    for host in net.hosts:
        host.lock = Lock()
        host.cmd("ping -c 1 10.0.0.1 &")

    # Gera arquivo JSON com dados da topologia
    print("\n*** Gerando arquivo de dados da topologia...")
    topology_data = generate_network_topology_data(topo, net)
    
    # Salva arquivo JSON
    json_filename = f"topology_data.json"
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), json_filename)
    
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(topology_data, f, indent=2, ensure_ascii=False)
        print(f"*** Dados da topologia salvos em: {json_filename}")
        print(f"    - Distâncias: {len(topology_data['distances'])}")
        print(f"    - Links com bandwidth: {len(topology_data['bandwidth'])}")
    except Exception as e:
        print(f"*** Erro ao salvar dados da topologia: {e}")

    if hasattr(topo, 'edge_switches') and hasattr(topo, 'backbone_switches'):
        info("*** RESUMO DA TOPOLOGIA ***\n")
        info("Controladores: {}\n".format(controllers))
        info("Switches de BORDA: {}\n".format([s['name'] for s in topo.edge_switches]))
        info("Switches de BACKBONE: {}\n".format([s['name'] for s in topo.backbone_switches]))
        info("Total de hosts: {}\n".format(len(net.hosts)))

    return net

if __name__ == '__main__':
    setLogLevel('info')
    
    # net = run(SimpleTopo())
    
    net = run(Tower())
    
    #LOCAL_GML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'brasil.gml')
    #net = run(GmlTopo(gml_file=LOCAL_GML_FILE))

    info("*** Iniciando CLI...\n")
    CLI(net)
    info("*** Parando a rede...\n")
    net.stop()