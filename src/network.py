#!/usr/bin/env python

from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import RemoteController
from mininet.log import setLogLevel
import sys

CONTROLERS = ["172.17.0.5", "172.17.0.6", "172.17.0.7"]

class SimpleTopo(Topo):
    def build(self):
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        s1 = self.addSwitch('s1', protocols='OpenFlow13')

        self.addLink(h1, s1)
        self.addLink(h2, s1)

def run():
    topo = SimpleTopo()

    net = Mininet(topo=topo, build=False, controller=None)

    # Adiciona múltiplos controladores
    for i, ip in enumerate(CONTROLERS):
        name = f"c{i}"
        c = RemoteController(name, ip=ip, port=6653)
        net.addController(c)

    net.build()
    net.start()

    print("Rede iniciada com os controladores {CONTROLERS}")
    net.pingAll()

    input("Pressione Enter para encerrar...")
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()
