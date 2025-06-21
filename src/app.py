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
    from network import *
    MININET_AVAILABLE = True
except ImportError:
    print("Mininet not detected - local network commands disabled")

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
        self.api = self.router.api
        
        self.commands = [
            {"name": "help", "function": self.help},
            {"name": "exit", "function": self.exit_app},
            {"name": "create_routes", "function": self.create_routes},
            {"name": "delete_routes", "function": self.delete_routes},
            {"name": "render_topology", "function": self.render_topology},
        ]
        
        if MININET_AVAILABLE:
            mininet_commands = [
                {"name": "simple_net", "function": self.simple_net},
                {"name": "tower_net", "function": self.tower_net},
                {"name": "gml_net", "function": self.gml_net},
                {"name": "ping_random", "function": self.ping_random},
                {"name": "ping_all", "function": self.ping_all},
                {"name": "iperf_random", "function": self.iperf_random},
                {"name": "traffic", "function": self.start_dummy_traffic},
                {"name": "clean_network", "function": self.clean_network},
            ]
            self.commands.extend(mininet_commands)
        

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
        if not MININET_AVAILABLE:
            print("Mininet not available - cleaning only flows")
            self.api.delete_all_flows()
            self.api.delete_inactive_devices()
            return
            
        print("Cleaning complete network...")
        self.api.delete_all_flows()

        if self.net:
            self.net.stop()

        self.net = None
        self.api.delete_inactive_devices()
        
        try:
            print("Running deep Mininet cleanup...")
            subprocess.run(['sudo', 'mn', '-c'], check=True, capture_output=True, text=True)
            print("Cleanup completed!")
        except subprocess.CalledProcessError as e:
            print(f"Warning: Mininet cleanup error: {e}")
        except FileNotFoundError:
            print("Warning: 'mn' command not found")

    def simple_net(self):
        if not MININET_AVAILABLE:
            print("Command requires Mininet!")
            return
        self.clean_network()
        self.net = run(SimpleTopo())

    def tower_net(self):
        if not MININET_AVAILABLE:
            print("Command requires Mininet!")
            return
        self.clean_network()
        self.net = run(Tower())

    def gml_net(self):
        if not MININET_AVAILABLE:
            print("Command requires Mininet!")
            return
        self.clean_network()
        gml_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'brasil.gml')
        self.net = run(GmlTopo(gml_file=gml_file))

    def help(self):
        for cmd in self.commands:
            print(cmd["name"])

    def exit_app(self):
        exit(0)

    def create_routes(self):
        print("Creating complete routes...")
        start = time.time()
        self.router.update()
        self.router.install_all_routes()
        total_time = time.time() - start
        print(f"Completed. Time spent: {total_time:.2f}s")

    def delete_routes(self):
        print("Deleting complete routes...")
        self.router.update()
        self.api.delete_all_flows()
        print("Completed.")

    def ping_random(self):
        if not MININET_AVAILABLE or not self.net:
            print("No active network!")
            return
        h1, h2 = random.sample(self.net.hosts, 2)
        results = self.net.ping([h1, h2])
        print(results)
        return results

    def ping_all(self):
        if not MININET_AVAILABLE or not self.net:
            print("Mininet not available or no network created!")
            return
        start = time.time()
        self.net.pingAll()
        total_time = time.time() - start
        print(f"Completed. Time spent: {total_time:.2f}s")

    def iperf_random(self):
        if not MININET_AVAILABLE or not self.net:
            print("No active network!")
            return
        h1, h2 = random.sample(self.net.hosts, 2)
        self.net.iperf([h1, h2])
	
    def start_dummy_traffic(self):
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
        render_topology()
        
def main():
    app = App()
    app.main_loop()

if __name__ == '__main__':
    main()