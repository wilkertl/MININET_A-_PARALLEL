#!/usr/bin/env python

from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import RemoteController
from mininet.log import setLogLevel

CONTROLERS = ["172.17.0.5", "172.17.0.6", "172.17.0.7"]

class SimpleTopo(Topo):
    def build(self):
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        s1 = self.addSwitch('s1', protocols='OpenFlow13')

        self.addLink(h1, s1)
        self.addLink(h2, s1)

def run():
    setLogLevel('info')
    topo = SimpleTopo()

    net = Mininet(topo=topo, build=False, controller=None, ipBase='10.0.0.0/8')

    # Adiciona múltiplos controladores
    for i, ip in enumerate(CONTROLERS):
        name = f"c{i}"
        c = RemoteController(name, ip=ip, port=6653)
        net.addController(c)

    net.build()
    net.start()

    # Descobrindo todos os hosts
    for host in net.hosts:
        host.cmd("ping -c1 10.0.0.1 &")

    return net

