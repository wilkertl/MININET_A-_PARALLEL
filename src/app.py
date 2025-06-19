from network import *
from router import Router
import os

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
            {"name": "create_routes", "function": self.create_routes}
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

    def ping_all(self):
        self.net.pingAll()

    def create_routes(self):
        self.router.update()
        self.router.install_all_routes()

def main():
    app = App()
    app.main_loop()

if __name__ == '__main__':
    main()
