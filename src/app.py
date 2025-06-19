from network import *
from routing import Router

class App():
    def __init__(self):
        self.net = None
        self.router = Router("127.0.0.1", 7001)
        self.commands = [
            {"name": "help", "function": self.help},
            {"name": "exit", "function": self.exit_app},
            {"name": "ping_all", "function": self.ping_all},
	        {"name": "simple_net", "function": self.simple_net},
            {"name": "tower_net", "function": self.tower_net},
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
            
        print("Command ({cmd}) not found.")
	
    def simple_net(self):
         if self.net:
             self.net.stop()

         self.net = run(SimpleTopo())

    def tower_net(self):
        if self.net:
             self.net.stop()

        self.net = run(Tower())


    def help(self):
        for cmd in self.commands:
            print(cmd["name"])

    def exit_app(self):
        if self.net:
             self.net.stop()

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
