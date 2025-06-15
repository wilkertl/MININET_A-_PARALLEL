#!/usr/bin/python3
"""
Este script integra uma topologia do TopoHub com o Mininet.

1. Baixa o arquivo de topologia GML (tata_nld.gml).
2. Lê o GML com NetworkX, usando as coordenadas 'lon' e 'lat'.
3. Define uma classe de Topologia customizada (GmlTopo) para o Mininet.
4. Dentro da GmlTopo:
   - Cada 'nó' do GML se torna um Switch.
   - Um Host é adicionado a cada Switch.
   - Cada 'aresta' do GML se torna um Link com parâmetros de banda (simulada)
     e delay (calculado a partir da distância geográfica).
5. Inicia a rede emulada e abre a CLI do Mininet para interação.
"""

import os
import sys
import random
import math
import re
import networkx as nx
import subprocess
import shutil

from mininet.net import Mininet
from mininet.node import OVSSwitch, Controller
from mininet.topo import Topo
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info, error

# --- CONFIGURAÇÕES ---
TOPOLOGY_FILE_URL = 'https://raw.githubusercontent.com/TopoHub/topologies/master/tata_nld.gml'
MAX_BACKBONE_BW_GBPS = 10.0
PROPAGATION_SPEED_KM_PER_MS = 200 # Velocidade da luz na fibra

def check_requirements():
    """Verifica se todos os requisitos estão instalados."""
    required_packages = ['mininet', 'networkx']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        error("Pacotes necessários não encontrados: {}\n".format(', '.join(missing_packages)))
        error("Por favor, instale-os usando: pip install " + " ".join(missing_packages))
        sys.exit(1)

def check_root():
    """Verifica se o script está sendo executado como root."""
    if os.geteuid() != 0:
        error("Este script precisa ser executado como root (sudo).\n")
        error("Por favor, execute: sudo python3 " + sys.argv[0])
        sys.exit(1)

def check_vm_environment():
    """Verifica se o ambiente é adequado para execução em VM."""
    # Verifica se está rodando em uma VM
    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
            if 'hypervisor' not in cpuinfo.lower():
                info("Aviso: Não detectado ambiente de virtualização. O script pode não funcionar corretamente.\n")
    except:
        info("Não foi possível verificar o ambiente de virtualização.\n")

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calcula a distância geodésica em km."""
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# A classe Topo customizada é a "ponte" entre NetworkX e Mininet
class GmlTopo(Topo):
    """
    Classe de topologia do Mininet que constrói a rede
    a partir de um arquivo GML do Topology Zoo/TopoHub.
    """
    def build(self, gml_file):
        info(f"*** Lendo topologia do arquivo: {gml_file}\n")
        # Lê o arquivo GML usando NetworkX (tentando 'id' e 'label')
        G = None
        try:
            G = nx.read_gml(gml_file, label='id')
        except Exception:
            G = nx.read_gml(gml_file, label='label')

        info("*** Adicionando switches e hosts...\n")
        switches = {}
        for node_id, node_data in G.nodes(data=True):
            # Usamos o ID do nó como nome do switch
            switch_name = str(node_id)
            switches[node_id] = self.addSwitch(switch_name)
            
            # Adiciona um host para cada switch para que a rede seja testável
            host_name = f"h{switch_name}"
            host = self.addHost(host_name)
            self.addLink(host, switches[node_id], bw=100) # Link host-switch com 100 Mbps

        info("*** Adicionando links entre switches com parâmetros de rede...\n")
        for u, v in G.edges():
            node1_data = G.nodes[u]
            node2_data = G.nodes[v]
            
            # Calcula o delay (latência) baseado na distância geográfica
            try:
                dist_km = haversine_distance(node1_data['lat'], node1_data['lon'],
                                             node2_data['lat'], node2_data['lon'])
                delay_ms = dist_km / PROPAGATION_SPEED_KM_PER_MS
            except KeyError:
                delay_ms = 1.0  # Delay padrão de 1ms se não houver coordenadas

            # Atribui banda aleatória (convertida para Mbps)
            bw_mbps = random.uniform(100.0, MAX_BACKBONE_BW_GBPS * 1000)

            # Adiciona o link entre os switches com os parâmetros calculados
            # O delay precisa ser uma string com unidade (ex: '0.5ms')
            self.addLink(
                switches[u], 
                switches[v], 
                bw=bw_mbps, 
                delay=f"{delay_ms:.2f}ms"
            )

def run_network():
    """
    Função principal para baixar, construir e rodar a rede no Mininet.
    """
    # Verifica requisitos antes de prosseguir
    check_requirements()
    check_root()
    check_vm_environment()

    file_name = TOPOLOGY_FILE_URL.split('/')[-1]
    if not os.path.exists(file_name):
        info(f"*** Baixando o arquivo da topologia: {file_name}...\n")
        try:
            subprocess.run(['wget', '-q', TOPOLOGY_FILE_URL], check=True)
        except subprocess.CalledProcessError:
            error(f"Falha ao baixar o arquivo {file_name}.\n")
            sys.exit(1)

    try:
        # Cria uma instância da nossa topologia customizada
        topo = GmlTopo(gml_file=file_name)

        # Inicia o Mininet
        net = Mininet(topo=topo,
                      switch=OVSSwitch,
                      link=TCLink,
                      controller=Controller,
                      autoSetMacs=True)

        info("*** Iniciando a rede...\n")
        net.start()

        info("*** Rede emulada está no ar! Iniciando a CLI do Mininet.\n")
        info("Use comandos como 'nodes', 'net', 'pingall'.\n")
        info("Para testar o delay, tente: 'h0 ping h100'.\n")
        CLI(net)

    except Exception as e:
        error(f"Erro durante a execução: {str(e)}\n")
        sys.exit(1)
    finally:
        info("*** Parando a rede...\n")
        if 'net' in locals():
            net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run_network()