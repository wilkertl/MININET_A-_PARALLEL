from itertools import permutations
from functools import partial
import random
from network import *
from router import Router
import re
from multiprocessing.dummy import Pool
from time import sleep
import threading
import os

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
            {"name": "simple_net", "function": self.simple_net},
            {"name": "tower_net", "function": self.tower_net},
            {"name": "ping_random", "function": self.ping_random},
            {"name": "ping_all", "function": self.ping_all},
            {"name": "iperf_random", "function": self.iperf_random},
            {"name": "create_routes", "function": self.create_routes},
            {"name": "traffic", "function": self.start_dummy_traffic},
            {"name": "gml_net", "function": self.gml_net},
            {"name": "clean_network", "function": self.clean_network},
            {"name": "create_routes", "function": self.create_routes}
        ]
        self.clean_network()
        

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
        self.api.delete_all_flows()

        if self.net:
            self.net.stop()

        self.net = None
        self.api.delete_inactive_devices()

    def simple_net(self):
        self.clean_network()
        self.net = run(SimpleTopo())

    def tower_net(self):
        self.clean_network()
        self.net = run(Tower())

    def gml_net(self):
        self.clean_network()
        gml_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tata_nld.gml')
        self.net = run(GmlTopo(gml_file=gml_file))

    def help(self):
        for cmd in self.commands:
            print(cmd["name"])

    def exit_app(self):
        self.clean_network()
        exit(0)

    def create_routes(self):
        self.router.update()
        self.router.install_all_routes()

    def ping_random(self):
        h1, h2 = random.sample(self.net.hosts, 2)
        pair = (h1, h2)

        results = self.net.ping(pair)
        print(results)
        return results

    def ping_all(self):
        self.net.pingAll()

    def iperf_random(self):
        h1, h2 = random.sample(self.net.hosts, 2)
        pair = (h1, h2)
        self.net.iperf(pair)
	
    def start_dummy_traffic(self):
        hosts = self.net.hosts[:]
        threads = []

        def worker(h1, h2):
            h1.cmd(f"iperf -c {h2.IP()} -u -t 20 -b 1G")

        pairs = unique_host_pairs(hosts)

        for h1, h2 in pairs:
            t = threading.Thread(target=worker, args=(h1, h2))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

def main():
    app = App()
    app.main_loop()

if __name__ == '__main__':
    main()
