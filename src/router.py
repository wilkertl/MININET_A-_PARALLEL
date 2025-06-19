import networkx as nx # type: ignore
from onos_api import OnosApi
import time

class Router():
    def __init__(self, onos_ip=None, port=None):
        self.hosts = None
        self.switches = None
        self.links = None
        self.api = OnosApi(onos_ip, port)
        self.update()

    def update(self):
        self.hosts = self.api.get_hosts()
        self.switches = self.api.get_switches()
        self.links = self.api.get_links()


    def find_port(self, src, dst):
        """
        Returns the port that connects switch src to device dst

        Args:
            src (str): e.g., "of:0000000000000001"
            dst (str): e.g., "of:0000000000000002" or "00:00:00:00:00:A1"
        """

        # if the link is beetween two switches
        for link in self.links:
            if link['src']['device'] == src and link['dst']['device'] == dst:
                return link['src']['port']
        
        # If the link is beetwween a switch and a host
        for host in self.hosts:
            if host['mac'] == dst and host['locations'][0]['elementId'] == src:
                return host['locations'][0]['port']

        return None


    def build_graph(self):
        G = nx.Graph()

        for switch in self.switches:
            G.add_node(switch)

        # Add host edges with weight = 1 (default)
        for host in self.hosts:
            switch = host['locations'][0]['elementId']
            G.add_node(host['mac'])
            G.add_edge(host['mac'], switch, weight=1.0)

        # Add switch-to-switch edges with weight based on distance/delay if available
        for link in self.links:
            src_device = link['src']['device']
            dst_device = link['dst']['device']
            
            # Tenta extrair informações de distância dos anotações do link
            weight = 1.0  # peso padrão
            
            # Se houver anotações com distância, usa como peso
            if 'annotations' in link and 'distance' in link['annotations']:
                try:
                    weight = float(link['annotations']['distance'])
                except (ValueError, TypeError):
                    weight = 1.0
            
            G.add_edge(src_device, dst_device, weight=weight)

        return G

    def create_flow(self, from_hop, to_hop, final_dst):
        """
        Create a flow that goes from "from_hop" to "to_hop" when trying to reach "final_dst¨

        Args:
            from_hop (str): Switch IDe.g. "of:0000000000000001"
            to_hop (str): Switch ID or MAC ADDR e.g. "of:0000000000000002" or "00:00:00:00:00:A1"
            final_dst (src): MAC ADDR e.g. "00:00:00:00:00:A1"
        """
        port = self.find_port(from_hop, to_hop)
        status, msg = self.api.push_flow(from_hop, final_dst, port)
        print(f"{status} -> {msg} for flow ({from_hop}, {to_hop}, {final_dst})")



    def heuristic(self, u, v):
        """
        Heurística para A*: usa distância real quando disponível no grafo,
        senão usa estimativa baseada na topologia da rede
        """
        # Se ambos são hosts (MAC addresses), distância mínima é 2 (host->switch->host)
        if ':' in u and len(u) == 17 and ':' in v and len(v) == 17:
            return 2.0 if u != v else 0.0
        
        # Se um é host e outro é switch, distância mínima é 1
        if ((':' in u and len(u) == 17) and ('of:' in v)) or (('of:' in u) and (':' in v and len(v) == 17)):
            return 1.0
        
        # Para switches, tenta usar distância real do grafo se disponível
        if 'of:' in u and 'of:' in v:
            # Verifica se temos o grafo construído para consultar distâncias
            if hasattr(self, '_graph_cache'):
                try:
                    # Tenta encontrar distância direta no grafo
                    if self._graph_cache.has_edge(u, v):
                        return self._graph_cache[u][v].get('weight', 1.0) * 0.8  # 80% da distância real como heurística
                    
                    # Se não há conexão direta, usa estimativa baseada em vizinhos comuns
                    u_neighbors = set(self._graph_cache.neighbors(u)) if self._graph_cache.has_node(u) else set()
                    v_neighbors = set(self._graph_cache.neighbors(v)) if self._graph_cache.has_node(v) else set()
                    
                    if u_neighbors & v_neighbors:  # Se têm vizinhos em comum
                        return 2.0  # Distância de 2 saltos
                    
                except:
                    pass
            
            # Fallback: estimativa baseada no ID do switch
            try:
                u_id = int(u.split(':')[-1], 16) % 100
                v_id = int(v.split(':')[-1], 16) % 100
                return float(abs(u_id - v_id))
            except:
                return 1.0
        
        return 1.0
    
    def install_all_routes(self):
        graph = self.build_graph()
        paths = []

        for src in self.hosts:
            for tgt in self.hosts:
                source = src['mac']
                target = tgt['mac']

                if source == target:
                    continue

                path = nx.astar_path(graph, source=source, target=target, heuristic=self.heuristic)
                paths.append(path) 

        for path in paths:
            final_dst = path[len(path) - 1]
            for i in range(len(path) - 1):
                hop = path[i]
                next_hop = path[i+1]

                if hop not in self.switches:
                    continue

                self.create_flow(from_hop=hop, to_hop=next_hop, final_dst=final_dst)

def main():
    print("Installing routing intents for all host pairs...")
    start = time.time()
    router = Router()
    print(router.hosts)
    print(router.switches)
    print(router.links)
    #router.install_all_routes()
    #total_time = time.time() - start
    print(f"Time spend to generate routs {total_time}")
    print("Done.")

if __name__ == "__main__":
    main()

