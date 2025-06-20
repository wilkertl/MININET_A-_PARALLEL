from network import *
from router import Router
import os
import time

class App():
    def __init__(self):
        self.net = None
        self.router = Router()
        self.api = self.router.api
        self.commands = [
            {"name": "help", "function": self.help},
            {"name": "exit", "function": self.exit_app},
            {"name": "ping_all", "function": self.ping_all},
	        {"name": "simple_net", "function": self.simple_net},
            {"name": "tower_net", "function": self.tower_net},
            {"name": "gml_net", "function": self.gml_net},
            {"name": "clean_network", "function": self.clean_network},
            {"name": "create_routes", "function": self.create_routes},
            {"name": "check_flows", "function": self.check_flows},
            {"name": "force_clean", "function": self.force_clean_onos}
        ]

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
        print("Limpando flows...")
        self.api.delete_all_flows()

        if self.net:
            print("Parando rede Mininet...")
            self.net.stop()

        self.net = None
        
        print("Forçando limpeza completa do ONOS...")
        import time
        time.sleep(2)
        
        # Remove dispositivos inativos
        self.api.delete_inactive_devices()
        time.sleep(3)
        
        # Remove todos os dispositivos registrados (forçado)
        self.force_clean_onos()
        
        print("Aguardando ONOS estabilizar...")
        time.sleep(10)

    def force_clean_onos(self):
        """Limpeza forçada do ONOS - remove TODOS os dispositivos"""
        import requests
        try:
            # Lista todos os dispositivos
            url = f"{self.api.BASE_URL}/devices"
            resp = requests.get(url, auth=self.api.AUTH)
            if resp.status_code == 200:
                devices = resp.json().get("devices", [])
                print(f"Removendo {len(devices)} dispositivos do ONOS...")
                
                for device in devices:
                    dev_id = device["id"]
                    del_url = f"{url}/{dev_id}"
                    del_resp = requests.delete(del_url, auth=self.api.AUTH)
                    if del_resp.status_code in (200, 204):
                        print(f"  Removido: {dev_id}")
                    else:
                        print(f"  Falha ao remover: {dev_id}")
            
            # Limpa hosts também
            host_url = f"{self.api.BASE_URL}/hosts"
            host_resp = requests.get(host_url, auth=self.api.AUTH)
            if host_resp.status_code == 200:
                hosts = host_resp.json().get("hosts", [])
                for host in hosts:
                    host_id = f"{host['mac']}/{host['vlan']}"
                    del_url = f"{host_url}/{host_id}"
                    requests.delete(del_url, auth=self.api.AUTH)
                    
        except Exception as e:
            print(f"Erro na limpeza forçada: {e}")

    def simple_net(self):
        self.clean_network()
        self.net = run(SimpleTopo())

    def tower_net(self):
        self.clean_network()
        self.net = run(Tower())

    def gml_net(self):
        self.clean_network()
        gml_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'brasil.gml')
        self.net = run(GmlTopo(gml_file=gml_file))

    def help(self):
        for cmd in self.commands:
            print(cmd["name"])

    def exit_app(self):
        self.clean_network()
        exit(0)

    def ping_all(self):
        self.net.pingAll()

    def create_routes(self):
        print("Limpando flows existentes...")
        self.api.delete_all_flows()
        print("Aguardando limpeza...")
        time.sleep(3)
        print("Criando rotas completas...")
        self.router.update()
        self.router.install_all_routes()
        print("Aguardando aplicação dos flows...")

    def check_flows(self):
        """Verifica status dos hosts e flows no ONOS"""
        print("=== DIAGNÓSTICO ===")
        hosts = self.api.get_hosts()
        print(f"Hosts descobertos: {len(hosts)}")
        for host in hosts:
            print(f"  {host['mac']} -> {host['locations'][0]['elementId']}")
        
        # Conta flows por dispositivo
        import requests
        url = f"{self.api.BASE_URL}/flows"
        resp = requests.get(url, auth=self.api.AUTH)
        if resp.status_code == 200:
            flows = resp.json().get('flows', [])
            flow_count = {}
            for flow in flows:
                device = flow['deviceId']
                flow_count[device] = flow_count.get(device, 0) + 1
            
            print("Flows por switch:")
            for device, count in flow_count.items():
                print(f"  {device}: {count} flows")
        print("=== FIM DIAGNÓSTICO ===")

def main():
    app = App()
    app.main_loop()

if __name__ == '__main__':
    main()
