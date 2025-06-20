#!/usr/bin/python
# -*- coding: utf-8 -*-

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

CONTROLERS = ["127.0.0.1"]

# Configurações para topologia GML
MAX_BACKBONE_BW_GBPS = 10.0
PROPAGATION_SPEED_KM_PER_MS = 200  # Velocidade da luz na fibra

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
        s1 = self.addSwitch('s1', protocols='OpenFlow13')

        self.addLink(h1, s1)
        self.addLink(h2, s1)

class Tower(Topo):
    def build(self):
        spines = [
            self.addSwitch('s1', protocols="OpenFlow13"),
            self.addSwitch('s2', protocols="OpenFlow13")
        ]

        self.addLink(spines[0], spines[1])

        leafs = [
            self.addSwitch('l1', protocols="OpenFlow13"),
            self.addSwitch('l2', protocols="OpenFlow13"),
            self.addSwitch('l3', protocols="OpenFlow13"),
            self.addSwitch('l4', protocols="OpenFlow13")
        ]

        for i in range(len(leafs)):
            leaf = leafs[i]
            self.addLink(leaf, spines[0])
            self.addLink(leaf, spines[1])

            for j in range(1, 6):
                host = self.addHost(f'h{j + i*5}')
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

        info("*** Adicionando switches e hosts...\n")
        switches = {}
        for node_id, node_data in G.nodes(data=True):
            switch_name = str(node_id)
            switches[node_id] = self.addSwitch(switch_name, protocols='OpenFlow13')
            
            host_name = "h{}".format(switch_name)
            host = self.addHost(host_name)
            self.addLink(host, switches[node_id], bw=100)

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

            bw_mbps = random.uniform(100.0, MAX_BACKBONE_BW_GBPS * 1000)

            self.addLink(
                switches[u], 
                switches[v], 
                bw=bw_mbps, 
                delay="{:.2f}ms".format(delay_ms)
            )

def run(topo):
    setLogLevel('info')

    # Configuração original com múltiplos controladores
    net = Mininet(topo=topo, build=False, controller=None, ipBase='10.0.0.0/8')
    net.build()
    sleep(1)

    # Adiciona múltiplos controladores
    for i, ip in enumerate(CONTROLERS):
        name = f"c{i}"
        c = RemoteController(name, ip=ip, port=6653)
        net.addController(c)

    net.start()
    sleep(1)

    # Descobrindo todos os hosts
    for host in net.hosts:
        host.cmd("ping -c1 10.0.0.1 &")

    return net

if __name__ == '__main__':
    # Exemplo de uso
    setLogLevel('info')
    
    # Para usar topologia simples com múltiplos controladores:
    # net = run(SimpleTopo())
    
    # Para usar topologia Tower:
    # net = run(Tower())
    
    # Para usar arquivo GML:
    LOCAL_GML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tata_nld.gml')
    net = run(GmlTopo(gml_file=LOCAL_GML_FILE))

