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

class Tower( Topo ):
    def build( self ):
        spines = [
            self.addSwitch('s1', protocols="OpenFlow13"),
            self.addSwitch('s2', protocols="OpenFlow13")
        ]

        self.addLink(spines[0], spines[1])

        leafs = [
            self.addSwitch('l1', protocols="OpenFlow13"),
            self.addSwitch('l2', protocols="OpenFlow13"),
            self.addSwitch('l3', protocols="OpenFlow13"),
            self.addSwitch('l4', protocols="OpenFlow13")
        ]

        for i in range(len(leafs)):
            leaf = leafs[i]
            self.addLink(leaf, spines[0])
            self.addLink(leaf, spines[1])

            for j in range(1, 6):
                host = self.addHost(f'h{j + i*5}')
                self.addLink(host, leaf)

def run(topo):
    setLogLevel('info')

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

