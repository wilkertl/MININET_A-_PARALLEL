from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import RemoteController
from mininet.log import setLogLevel
from threading import Lock
from onos_api import OnosApi
from time import sleep

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
            self.addSwitch( 's1' ),
            self.addSwitch( 's2' )
       ]

        # Now create the leaf switches, their hosts and connect them together
        for i in range(4):
            sn = i + 1
            leaf = self.addSwitch(f's1{sn}')
            for spine in spines:
                self.addLink(leaf, spine)

            for j in range(5):
                host = self.addHost(f'h{sn}{j+1}')
                self.addLink( host, leaf )

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

    sleep(10)

    # Descobrindo todos os hosts
    for host in net.hosts:
        host.lock = Lock()
        host.cmd("ping -c 1 10.0.0.1 &")

    return net

