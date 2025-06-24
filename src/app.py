import random
from router import Router
import threading
import time
import os
import subprocess
from render_topology import render_topology

# Detect if Mininet is available
MININET_AVAILABLE = False
try:
    import mininet
    from network import *
    MININET_AVAILABLE = True
except ImportError:
    from network_mock import *

# Detect if PyCUDA is available
PYCUDA_AVAILABLE = False
try:
    from router_pycuda import RouterPyCUDA
    PYCUDA_AVAILABLE = True
except ImportError:
    pass

def unique_host_pairs(hosts):
    random.shuffle(hosts)
    pairs = []
    for i in range(0, len(hosts) - 1, 2):
        pairs.append((hosts[i], hosts[i+1]))
    return pairs

class App():
    def __init__(self):
        self.net = None
        self.router = Router()
        self.router_pycuda = RouterPyCUDA() if PYCUDA_AVAILABLE else None
        self.api = self.router.api
        
        self.commands = [
            {"name": "help", "function": self.help},
            {"name": "exit", "function": self.exit_app},
            {"name": "create_routes", "function": self.create_routes},
            {"name": "create_routes_parallel", "function": self.create_routes_parallel},
            {"name": "delete_routes", "function": self.delete_routes},
            {"name": "render_topology", "function": self.render_topology},
        ]
       
        # Add PyCUDA command only if PyCUDA is available
        if PYCUDA_AVAILABLE:
            self.commands.append({"name": "create_routes_pycuda", "function": self.create_routes_pycuda})
        
        # Network commands - work with both Mininet and Mock
        network_commands = [
            {"name": "simple_net", "function": self.simple_net},
            {"name": "tower_net", "function": self.tower_net},
            {"name": "gml_net", "function": self.gml_net},
            {"name": "clean_network", "function": self.clean_network},
        ]
        
        if MININET_AVAILABLE:
            # Additional Mininet-only commands
            mininet_only_commands = [
                {"name": "ping_random", "function": self.ping_random},
                {"name": "ping_all", "function": self.ping_all},
                {"name": "iperf_random", "function": self.iperf_random},
                {"name": "traffic", "function": self.start_dummy_traffic},
            ]
            network_commands.extend(mininet_only_commands)
        
        self.commands.extend(network_commands)
        

    def main_loop(self):
        print("""Type "help" to see a list of possible commands """)
        while True:
            cmd = input("A*> ")
            fun = self.get_function(cmd)

            if fun:
                fun()

    def get_function(self, cmd):
        for command in self.commands:
            if command["name"] == cmd:
                return command["function"]
            
        print(f"Command ({cmd}) not found.")

    def clean_network(self):
        """Clean up network and flows"""
        if not MININET_AVAILABLE:
            print("Mock: Cleaning network and flows")
            self.api.delete_inactive_devices()
            self.net = None
            return
        
        if self.net:
            self.net.stop()

        try:
            subprocess.run(['sudo', 'mn', '-c'], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError:
            pass
        except FileNotFoundError:
            pass
        
        self.net = None
        self.api.delete_inactive_devices()

    def _create_network(self, topo_class, network_name, *args, **kwargs):
        """Create network with Mininet or Mock automatically"""
        self.clean_network()
        
        if MININET_AVAILABLE:
            print(f"Creating {network_name} with Mininet...")
            topo = topo_class(*args, **kwargs)
            self.net = run(topo)
            print(f"{network_name} created successfully!")
        else:
            print(f"Mininet not available. Creating mock {network_name}...")
            mock_topo = topo_class()
            
            if args or kwargs:
                mock_topo.build(*args, **kwargs)
            else:
                mock_topo.build()
            
            self.net = run(mock_topo)
            
            if hasattr(self.api, 'update_from_network_mock'):
                self.api.update_from_network_mock(self.net)
                print(f"Mock {network_name} created! {len(self.api.get_hosts())} hosts, {len(self.api.get_switches())} switches, {len(self.api.get_links())} links")
            
            self.router.topology_data = self.router.load_topology_data()
            print(f"Router: Reloaded topology data after mock network creation")

    def simple_net(self):
        self._create_network(SimpleTopo, "Simple Network")

    def tower_net(self):
        self._create_network(Tower, "Tower Network", num_spines=10, num_leafs=25, hosts_per_leaf=25)

    def gml_net(self):
        gml_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'brasil.gml')
        self._create_network(GmlTopo, "GML Network", gml_file=gml_file)

    def help(self):
        for cmd in self.commands:
            print(cmd["name"])

    def exit_app(self):
        if MININET_AVAILABLE:
            self.clean_network()
        exit(0)

    def create_routes(self):
        start = time.time()
        self.router.update()
        self.router.install_all_routes(parallel=False)
        total_time = time.time() - start
        print(f"Completed. Time spent: {total_time:.2f}s")

    def create_routes_parallel(self):
        start = time.time()
        self.router.update()
        self.router.install_all_routes(parallel=True)
        total_time = time.time() - start
        print(f"Completed. Time spent: {total_time:.2f}s")

    def create_routes_pycuda(self):
        if not PYCUDA_AVAILABLE or not self.router_pycuda:
            print("PyCUDA não disponível - comando PyCUDA não habilitado")
            return
        
        start = time.time()
        self.router_pycuda.update()
        self.router_pycuda.install_all_routes_pycuda()
        total_time = time.time() - start
        print(f"Completed. Time spent: {total_time:.2f}s")

    def delete_routes(self):
        self.api.delete_all_flows()
        print("Completed.")

    def ping_random(self):
        """Ping between two random hosts"""
        if not MININET_AVAILABLE or not self.net:
            print("No active network!")
            return
        h1, h2 = random.sample(self.net.hosts, 2)
        results = self.net.ping([h1, h2])
        print(results)
        return results

    def ping_all(self):
        """Ping all hosts to test connectivity"""
        if not MININET_AVAILABLE or not self.net:
            print("Mininet not available or no network created!")
            return
        start = time.time()
        self.net.pingAll()
        total_time = time.time() - start
        print(f"Completed. Time spent: {total_time:.2f}s")

    def iperf_random(self):
        """Run iperf between two random hosts"""
        if not MININET_AVAILABLE or not self.net:
            print("No active network!")
            return
        h1, h2 = random.sample(self.net.hosts, 2)
        self.net.iperf([h1, h2])
	
    def start_dummy_traffic(self):
        """Start dummy traffic between all host pairs"""
        if not MININET_AVAILABLE or not self.net:
            print("No active network!")
            return
        hosts = self.net.hosts[:]
        threads = []

        def worker(h1, h2):
            with h1.lock:
                h1.cmd(f"iperf -c {h2.IP()} -u -t 20 -b 10M")

        pairs = unique_host_pairs(hosts)

        for h1, h2 in pairs:
            t = threading.Thread(target=worker, args=(h1, h2))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()
        
    def render_topology(self):
        """Render network topology visualization"""
        render_topology()



def main():
    app = App()
    app.main_loop()

if __name__ == '__main__':
    main()