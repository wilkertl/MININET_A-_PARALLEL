import networkx as nx
import requests
from itertools import combinations
import time

from onos_api import OnosApi 

class Router():
    def __init__(self, onos_ip='127.0.0.1', port=8181):
        self.api = OnosApi(onos_ip, port)
        self.hosts = []
        self.switches = []
        self.links = []             
        
        self.update()

    def update(self):
        """Atualiza a topologia da rede a partir do ONOS."""
        self.hosts = self.api.get_hosts()
        self.switches = self.api.get_switches()
        self.links = self.api.get_links()

    def find_port(self, src, dst):
        """Encontra a porta de conexão entre dois dispositivos."""
        for link in self.links:
            if link['src']['device'] == src and link['dst']['device'] == dst:
                return link['src']['port']
        for host in self.hosts:
            if host['mac'] == dst and host['locations'][0]['elementId'] == src:
                return host['locations'][0]['port']
        return None
    
    def build_graph(self):
        """
        Constrói um grafo da topologia de forma robusta, usando apenas os
        dados de conexão para evitar inconsistências de identificadores.
        """
        G = nx.Graph()
        if not self.hosts:
            print("AVISO: Nenhum host encontrado. O grafo pode estar vazio.")
        for host in self.hosts:
            try:
                host_mac = host['mac']
                switch_id = host['locations'][0]['elementId']
                G.add_edge(host_mac, switch_id)
            except (KeyError, IndexError):
                print(f"AVISO: Host com dados malformados ignorado: {host}")
        
        if not self.links:
            print("AVISO: Nenhum link entre switches encontrado. A rede pode estar particionada.")
        for link in self.links:
            try:
                G.add_edge(link['src']['device'], link['dst']['device'])
            except KeyError:
                print(f"AVISO: Link com dados malformados ignorado: {link}")
        return G

    def install_all_routes(self):
        """
        Instala rotas unicast PROATIVAS e PERMANENTES, imitando a especificidade
        das regras reativas do ONOS com IN_PORT + ETH_SRC + ETH_DST.
        """
        
        graph = self.build_graph()
        unique_flows_final = set()

        host_macs = [host['mac'] for host in self.hosts]
        
        for source_mac, target_mac in combinations(host_macs, 2):
            try:
                path = nx.shortest_path(graph, source=source_mac, target=target_mac)
                
                for i in range(1, len(path) - 1): 
                    if path[i] in [s for s in self.switches]:  
                        in_port = self.find_port(path[i], path[i-1])  
                        out_port = self.find_port(path[i], path[i+1])  
                        
                        if in_port and out_port:
                            unique_flows_final.add((
                                path[i], in_port, out_port, 
                                10, target_mac, source_mac
                            ))
                
                reversed_path = list(reversed(path))
                for i in range(1, len(reversed_path) - 1):
                    if reversed_path[i] in [s for s in self.switches]:
                        in_port = self.find_port(reversed_path[i], reversed_path[i-1])
                        out_port = self.find_port(reversed_path[i], reversed_path[i+1])
                        
                        if in_port and out_port:
                            unique_flows_final.add((
                                reversed_path[i], in_port, out_port,
                                10, source_mac, target_mac
                            ))

            except nx.NetworkXNoPath:
                print(f"AVISO: Não há caminho entre {source_mac} e {target_mac}")

        all_flows_unique = []
        for switch, in_port, out_port, priority, dst, src in unique_flows_final:
            all_flows_unique.append({
                'switch_id': switch,
                'output_port': out_port,
                'priority': priority,
                'isPermanent': True,
                'eth_dst': dst,
                'eth_src': src,
                'in_port': in_port
            })

        if not all_flows_unique:
            print("Nenhum flow para criar.")
            return

        start_time = time.time()
        results = self.api.push_flows_batch(all_flows_unique)
        success_count = sum(1 for status, _ in results if status == 201)
        total_time = time.time() - start_time
        
        print(f"✓ Criação concluída: {success_count}/{len(all_flows_unique)} flows em {total_time:.2f}s")