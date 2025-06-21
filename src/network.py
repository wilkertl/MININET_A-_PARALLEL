import os
import sys
import math
import random
import networkx as nx
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
MIN_BACKBONE_BW_MBPS = 10.0  
MAX_BACKBONE_BW_MBPS = 100.0  
PROPAGATION_SPEED_KM_PER_MS = 200  
MIN_HOSTS_PER_EDGE_SWITCH = 1
MAX_HOSTS_PER_EDGE_SWITCH = 7
EDGE_SWITCH_DEGREE_THRESHOLD = 2  
LOW_LINK_CHANCE = 0.20 
HOST_BW_MBPS = 10.0

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

class SimpleTopo(Topo):
    def build(self):
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        s1 = self.addSwitch('s1', dpid=make_dpid(1), protocols='OpenFlow13')

        self.addLink(h1, s1)
        self.addLink(h2, s1)

class Tower( Topo ):
    def build( self ):
        spines = [
            self.addSwitch('s1', dpid=make_dpid(1), protocols="OpenFlow13"),
            self.addSwitch('s2', dpid=make_dpid(2), protocols="OpenFlow13")
        ]

        self.addLink(spines[0], spines[1])

        leafs = []
        for i in range(4):
            leaf = self.addSwitch(f'l{i+1}', dpid=make_dpid(10 + i), protocols="OpenFlow13")
            leafs.append(leaf)

        for i, leaf in enumerate(leafs):
            self.addLink(leaf, spines[0])
            self.addLink(leaf, spines[1])

            for j in range(1, 6):
                host = self.addHost(f'h{j + i * 5}')
                self.addLink(host, leaf)

class GmlTopo(Topo):
    """
    Classe de topologia do Mininet que constroi a rede
    a partir de um arquivo GML local.
    """
    def build(self, gml_file):
        info("*** Lendo topologia do arquivo: {}\n".format(gml_file))
        G = None
        try:
            G = nx.read_gml(gml_file, label='id')
        except Exception:
            G = nx.read_gml(gml_file, label='label')

        info("*** Adicionando switches...\n")
        switches = {}
        self.edge_switches = []
        self.backbone_switches = []
        
        for idx, (node_id, node_data) in enumerate(G.nodes(data=True)):
            switch_name = str(node_id)
            dpid = make_dpid(idx + 1)
            switch_ref = self.addSwitch(switch_name, dpid=dpid, protocols='OpenFlow13')
            switches[node_id] = switch_ref

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

        info("*** Switches de BORDA ({}): {}\n".format(
            len(self.edge_switches), 
            [s['name'] for s in self.edge_switches]
        ))
        info("*** Switches de BACKBONE ({}): {}\n".format(
            len(self.backbone_switches),
            [s['name'] for s in self.backbone_switches]
        ))

        info("*** Adicionando hosts aos switches de borda...\n")
        total_hosts = 0
        for edge_switch in self.edge_switches:
            num_hosts = random.randint(MIN_HOSTS_PER_EDGE_SWITCH, MAX_HOSTS_PER_EDGE_SWITCH)
            info("Adicionando {} hosts ao switch de borda {}\n".format(num_hosts, edge_switch['name']))
            
            for i in range(num_hosts):
                host_name = "h{}-s{}".format(total_hosts + 1, edge_switch['name'])
                host = self.addHost(host_name)
                self.addLink(host, switches[edge_switch['id']], bw=HOST_BW_MBPS)
                total_hosts += 1

        info("*** Total de hosts adicionados: {}\n".format(total_hosts))

        info("*** Adicionando links entre switches com parametros de rede...\n")
        for u, v in G.edges():
            node1_data = G.nodes[u]
            node2_data = G.nodes[v]
            
            try:
                dist_km = haversine_distance(node1_data['lat'], node1_data['lon'],
                                             node2_data['lat'], node2_data['lon'])
                delay_ms = dist_km / PROPAGATION_SPEED_KM_PER_MS
            except KeyError:
                delay_ms = 1.0


            if random.uniform(0, 1) < LOW_LINK_CHANCE:
                bw_mbps = MIN_BACKBONE_BW_MBPS
            else:
                bw_mbps = MAX_BACKBONE_BW_MBPS
            
            switch_u_name = switches[u] if isinstance(switches[u], str) else str(switches[u])
            switch_v_name = switches[v] if isinstance(switches[v], str) else str(switches[v])
            
            info("Link {}-{}: BW={:.1f}Mbps, Delay={:.2f}ms\n".format(
                switch_u_name, switch_v_name, bw_mbps, delay_ms))
            
            self.addLink(
                switches[u],
                switches[v],
                bw=bw_mbps,
                delay="{:.2f}ms".format(delay_ms),
                loss=0.1,  
                max_queue_size=100,
                use_htb=True
            )

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