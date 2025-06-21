from itertools import permutations
from functools import partial
import random
from router import Router
import threading
import time
import os
import subprocess

# Detecta se o Mininet está disponível
MININET_AVAILABLE = False
try:
    from network import *
    MININET_AVAILABLE = True
except ImportError:
    print("Mininet não detectado - comandos de rede local desabilitados")

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
            print("Mininet não disponível - limpando apenas flows")
            self.api.delete_all_flows()
            self.api.delete_inactive_devices()
            return
            
        print("Limpando rede completa...")
        self.api.delete_all_flows()

        if self.net:
            self.net.stop()

        self.net = None
        self.api.delete_inactive_devices()
        
        # Equivalente ao sudo mn -c
        try:
            print("Executando limpeza profunda do Mininet...")
            subprocess.run(['sudo', 'mn', '-c'], check=True, capture_output=True, text=True)
            print("Limpeza concluída!")
        except subprocess.CalledProcessError as e:
            print(f"Aviso: Erro na limpeza do Mininet: {e}")
        except FileNotFoundError:
            print("Aviso: Comando 'mn' não encontrado")

    def simple_net(self):
        if not MININET_AVAILABLE:
            print("Comando requer Mininet!")
            return
        self.clean_network()
        self.net = run(SimpleTopo())

    def tower_net(self):
        if not MININET_AVAILABLE:
            print("Comando requer Mininet!")
            return
        self.clean_network()
        self.net = run(Tower())

    def gml_net(self):
        if not MININET_AVAILABLE:
            print("Comando requer Mininet!")
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
        print("Criando rotas completas...")
        start = time.time()
        self.router.update()
        self.router.install_all_routes()
        total_time = time.time() - start
        print(f"Time spend to create routes {total_time}")
        print("Done.")

    def delete_routes(self):
        print("Deletando rotas completas...")
        start = time.time()
        self.router.update()
        self.api.delete_all_flows()

    def ping_random(self):
        if not MININET_AVAILABLE or not self.net:
            print("Nenhuma rede ativa!")
            return
        h1, h2 = random.sample(self.net.hosts, 2)
        pair = (h1, h2)

        results = self.net.ping(pair)
        print(results)
        return results

    def ping_all(self):
        if not MININET_AVAILABLE or not self.net:
            print("Mininet não disponível ou rede não criada!")
            return
        start = time.time()
        self.net.pingAll()
        total_time = time.time() - start
        print(f"Time spend to ping all {total_time}")
        print("Done.")

    def iperf_random(self):
        if not MININET_AVAILABLE or not self.net:
            print("Nenhuma rede ativa!")
            return
        h1, h2 = random.sample(self.net.hosts, 2)
        pair = (h1, h2)
        self.net.iperf(pair)
	
    def start_dummy_traffic(self):
        if not MININET_AVAILABLE or not self.net:
            print("Nenhuma rede ativa!")
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
        
def main():
    app = App()
    app.main_loop()

if __name__ == '__main__':
    main()