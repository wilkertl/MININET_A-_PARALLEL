from itertools import permutations
from functools import partial
import random
from network import *
from router import Router
import re
from multiprocessing.dummy import Pool
import time

cpu_count=3

def iperf_test(pair, net, udp=False, time_sec=5, bandwidth='10M'):
    src_name, dst_name = pair
    src = net.get(src_name)
    dst = net.get(dst_name)
    proto = 'UDP' if udp else 'TCP'
    
    # Start iperf server on dst
    dst.cmd('killall -9 iperf')
    arg = '-u' if udp else ''
    dst.cmd(f'iperf -s {arg} &')
    time.sleep(1)  # Wait for server to start

    # Run iperf client from src
    cmd = f'iperf -c {dst.IP()} -t {time_sec}'
    if udp:
        cmd += f' -u -b {bandwidth}'

    output = src.cmd(cmd)
    dst.cmd('killall -9 iperf')  # Stop server

    result = {
        'src': src.name,
        'dst': dst.name,
        'protocol': proto,
        'bandwidth': None,
        'jitter': None,
        'loss': None
    }

    # Parse output
    if udp:
        match = re.search(r'([\d.]+)\s+Mbits/sec\s+([\d.]+)\s+ms\s+(\d+)/(\d+)', output)
        if match:
            bw, jitter, lost, total = match.groups()
            result.update({
                'bandwidth': float(bw),
                'jitter': float(jitter),
                'loss': 100 * int(lost) / int(total)
            })
    else:
        match = re.search(r'([\d.]+)\s+Mbits/sec', output)
        if match:
            result['bandwidth'] = float(match.group(1))

    return result

def ping_pair(pair, net):
    src_name, dst_name = pair
    src = net.get(src_name)
    dst = net.get(dst_name)
    cmd = f'ping -c 3 {dst.IP()}'
    output = src.cmd(cmd)

    # Packet loss
    loss_match = re.search(r'(\d+)% packet loss', output)
    loss = int(loss_match.group(1)) if loss_match else None

    # RTT
    rtt_match = re.search(r'rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)', output)
    if rtt_match:
        rtt_min, rtt_avg, rtt_max, rtt_mdev = map(float, rtt_match.groups())
    else:
        rtt_min = rtt_avg = rtt_max = rtt_mdev = None

    return {
        'src': src.name,
        'dst': dst.name,
        'loss': loss,
        'rtt_min': rtt_min,
        'rtt_avg': rtt_avg,
        'rtt_max': rtt_max,
        'rtt_mdev': rtt_mdev
    }

class App():
    def __init__(self):
        self.net = None
        self.router = Router("127.0.0.1", 7001)
        self.api = self.router.api
        self.commands = [
            {"name": "help", "function": self.help},
            {"name": "exit", "function": self.exit_app},
            {"name": "ping_all", "function": self.ping_all},
	        {"name": "simple_net", "function": self.simple_net},
            {"name": "tower_net", "function": self.tower_net},
            {"name": "create_routes", "function": self.create_routes},
            {"name": "ping", "function": self.ping_all_parallel},
            {"name": "iperf_tcp", "function": self.run_iperf},
            {"name": "iperf_udp", "function": self.run_iperf_udp}
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
    
    def ping_all_parallel(self):
        hosts_names = [host.name for host in self.net.hosts]
        pairs = [(h1, h2) for h1 in hosts_names for h2 in hosts_names if h1 != h2]

        f = partial(ping_pair, net=self.net)

        with Pool(processes=min(cpu_count, len(pairs))) as pool:
            results = pool.map(f, pairs)
      
        print(results)
        return results

    def run_iperf_udp(self):
        return self.run_iperf_tcp(udp=True)

    def run_iperf(self, udp=False):
        hosts_names = [host.name for host in self.net.hosts]
        pairs = list(permutations(hosts_names, 2))  # (src, dst), no self-pairs

        random.shuffle(pairs)
        f = partial(iperf_test, net=self.net, udp=udp)

        with Pool(processes=min(cpu_count, len(pairs))) as pool:
            results = pool.map(f, pairs)

        print(results)
        return results


def main():
    app = App()
    app.main_loop()

if __name__ == '__main__':
    main()