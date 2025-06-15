#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Este script integra uma topologia LOCAL (arquivo GML) com o Mininet.
"""

import os
import sys
import math
import random
import networkx as nx
import subprocess

# Adiciona o caminho da biblioteca Mininet para o sudo
sys.path.append('/home/sdn/mininet')

from mininet.net import Mininet
from mininet.node import OVSSwitch, Controller
from mininet.topo import Topo
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info, error

# --- CONFIGURACOES ---
# <<< MUITO IMPORTANTE: Coloque o nome do seu arquivo GML local aqui!
# O arquivo deve estar na mesma pasta que este script (src/)
LOCAL_GML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tata_nld.gml')

MAX_BACKBONE_BW_GBPS = 10.0
PROPAGATION_SPEED_KM_PER_MS = 200 # Velocidade da luz na fibra

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calcula a distancia geodesica em km."""
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

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
            switches[node_id] = self.addSwitch(switch_name)
            
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

def run_network():
    """
    Funcao principal para construir e rodar a rede no Mininet.
    """
    if os.geteuid() != 0:
        error("Este script precisa ser executado como root (sudo).\n")
        sys.exit(1)

    if not os.path.exists(LOCAL_GML_FILE):
        error("Arquivo GML nao encontrado em: {}\n".format(LOCAL_GML_FILE))
        error("Por favor, verifique se o nome do arquivo esta correto e se ele esta na mesma pasta que o script.\n")
        sys.exit(1)

    try:
        topo = GmlTopo(gml_file=LOCAL_GML_FILE)

        net = Mininet(topo=topo,
                      switch=OVSSwitch,
                      link=TCLink,
                      controller=Controller,
                      autoSetMacs=True)

        info("*** Iniciando a rede...\n")
        net.start()

        info("*** Rede emulada esta no ar! Iniciando a CLI do Mininet.\n")
        CLI(net)

    except Exception as e:
        # Usamos 'as e' para compatibilidade com Python 2 e 3
        error("Erro durante a execucao: {}\n".format(e))
        if 'net' in locals():
            net.stop()
        sys.exit(1)
    finally:
        info("*** Parando a rede...\n")
        # Garante que a rede seja parada mesmo se a CLI falhar
        if 'net' in locals() and net.terms:
             net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run_network()
