import network

class App():
    def __init__(self, net):
        self.net = net
        self.commands = [
            {"name": "help", "function": self.help},
            {"name": "exit", "function": self.exit_app},
            {"name": "start", "function": self.start}
        ]

    def main_loop(self):
        print("""Type "help" to see a list of possible commands """)
        while True:
            cmd = input("A*> ")
            fun = self.get_function(cmd)
            fun()

    def get_function(self, cmd):
        for command in self.commands:
            if command["name"] == cmd:
                return command["function"]
            
        print("Command ({cmd}) not found.")

    def help(self):
        for cmd in self.commands:
            print(cmd["name"])

    def exit_app(self):
        self.net.stop()
        exit(0)

    def start(self):
        self.net.pingAll()

def main():
    net = network.run()
    app = App(net)
    app.main_loop()

if __name__ == '__main__':
    main()