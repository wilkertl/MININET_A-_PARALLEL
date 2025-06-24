import json
import os
import random
import time
from dotenv import load_dotenv

load_dotenv()

class OnosApiMock:
    """Mock ONOS API for testing environment"""
    
    def __init__(self, onos_ip=None, port=None, username=None, password=None):
        self.onos_ip = onos_ip or os.getenv('ONOS_IP', '127.0.0.1')
        self.port = port or os.getenv('ONOS_PORT', '8181')
        self.username = username or os.getenv('ONOS_USER', 'onos')
        self.password = password or os.getenv('ONOS_PASSWORD', 'rocks')
        
        self.BASE_URL = f"http://{self.onos_ip}:{self.port}/onos/v1"
        self.APP_ID = "org.onosproject.cli"
        
        self.mock_hosts = []
        self.mock_switches = []
        self.mock_links = []
        self.mock_flows = {}
        self.flow_id_counter = 1
        
        self._load_topology_data()
        
    def _load_topology_data(self):
        """Load topology data from mock network"""
        topology_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'topology_data_mock.json')
        
        if os.path.exists(topology_file):
            try:
                with open(topology_file, 'r', encoding='utf-8') as f:
                    topology_data = json.load(f)
                self._generate_mock_data_from_topology(topology_data)
            except Exception as e:
                print(f"Mock: Error loading topology data: {e}")
                self._generate_default_mock_data()
        else:
            self._generate_default_mock_data()
    
    def _generate_mock_data_from_topology(self, topology_data):
        """Generate mock data based on topology"""
        
        switches_found = set()
        hosts_found = set()
        
        for key in topology_data.get("bandwidth", {}):
            parts = key.split('-')
            if len(parts) == 2:
                node1, node2 = parts
                
                if self._is_ip_format(node1):
                    hosts_found.add(node1)
                elif len(node1) == 16 and all(c in '0123456789abcdef' for c in node1.lower()):
                    switches_found.add(node1)
                
                if self._is_ip_format(node2):
                    hosts_found.add(node2)
                elif len(node2) == 16 and all(c in '0123456789abcdef' for c in node2.lower()):
                    switches_found.add(node2)
        
        self.mock_switches = []
        for i, switch_dpid in enumerate(sorted(switches_found)):
            self.mock_switches.append(f"of:{switch_dpid}")
        
        self.mock_hosts = []
        for i, host_ip in enumerate(sorted(hosts_found)):
            ip_parts = host_ip.split('.')
            mac = f"02:00:{int(ip_parts[0]):02x}:{int(ip_parts[1]):02x}:{int(ip_parts[2]):02x}:{int(ip_parts[3]):02x}"
            
            connected_switch = None
            for key, bandwidth in topology_data.get("bandwidth", {}).items():
                if host_ip in key:
                    other_node = key.replace(host_ip, '').replace('-', '')
                    if len(other_node) == 16:
                        connected_switch = f"of:{other_node}"
                        break
            
            if not connected_switch and self.mock_switches:
                connected_switch = self.mock_switches[i % len(self.mock_switches)]
            
            host_data = {
                "id": f"{mac}/{host_ip}",
                "mac": mac,
                "vlan": "-1",
                "innerVlan": "-1", 
                "outerTpid": "unknown",
                "configured": False,
                "suspended": False,
                "ipAddresses": [host_ip],
                "locations": [
                    {
                        "elementId": connected_switch,
                        "port": str(i + 1)
                    }
                ]
            }
            self.mock_hosts.append(host_data)
        
        self.mock_links = []
        link_id_counter = 1
        
        for key, bandwidth in topology_data.get("bandwidth", {}).items():
            parts = key.split('-')
            if len(parts) == 2:
                node1, node2 = parts
                
                if (len(node1) == 16 and len(node2) == 16 and 
                    all(c in '0123456789abcdef' for c in node1.lower()) and
                    all(c in '0123456789abcdef' for c in node2.lower())):
                    
                    switch1 = f"of:{node1}"
                    switch2 = f"of:{node2}"
                    
                    port1 = str((link_id_counter % 10) + 10)
                    port2 = str((link_id_counter % 10) + 20)
                    
                    link_data = {
                        "src": {
                            "device": switch1,
                            "port": port1
                        },
                        "dst": {
                            "device": switch2,
                            "port": port2  
                        },
                        "type": "DIRECT",
                        "state": "ACTIVE",
                        "durable": True
                    }
                    self.mock_links.append(link_data)
                    link_id_counter += 1
        
       
    def _is_ip_format(self, text):
        """Check if text is in IP format"""
        parts = text.split('.')
        if len(parts) != 4:
            return False
        try:
            for part in parts:
                num = int(part)
                if not 0 <= num <= 255:
                    return False
            return True
        except ValueError:
            return False
    
    def _generate_default_mock_data(self):
        """Generate default mock data when no topology available"""
        
        self.mock_switches = [
            "of:0000000000000001",
            "of:0000000000000002", 
            "of:000000000000000b",
            "of:000000000000000c"
        ]
        
        self.mock_hosts = [
            {
                "id": "02:00:0A:00:00:02/10.0.0.2",
                "mac": "02:00:0A:00:00:02",
                "vlan": "-1",
                "innerVlan": "-1",
                "outerTpid": "unknown", 
                "configured": False,
                "suspended": False,
                "ipAddresses": ["10.0.0.2"],
                "locations": [{"elementId": "of:000000000000000b", "port": "1"}]
            },
            {
                "id": "02:00:0A:00:00:03/10.0.0.3", 
                "mac": "02:00:0A:00:00:03",
                "vlan": "-1",
                "innerVlan": "-1",
                "outerTpid": "unknown",
                "configured": False,
                "suspended": False, 
                "ipAddresses": ["10.0.0.3"],
                "locations": [{"elementId": "of:000000000000000c", "port": "1"}]
            }
        ]
        
        self.mock_links = [
            {
                "src": {"device": "of:0000000000000001", "port": "10"},
                "dst": {"device": "of:0000000000000002", "port": "20"},
                "type": "DIRECT",
                "state": "ACTIVE", 
                "durable": True
            },
            {
                "src": {"device": "of:000000000000000b", "port": "11"},
                "dst": {"device": "of:0000000000000001", "port": "21"},
                "type": "DIRECT",
                "state": "ACTIVE",
                "durable": True  
            },
            {
                "src": {"device": "of:000000000000000c", "port": "12"},
                "dst": {"device": "of:0000000000000002", "port": "22"},
                "type": "DIRECT", 
                "state": "ACTIVE",
                "durable": True
            }
        ]

    def get_hosts(self):
        """Get all hosts from mock ONOS"""
        return self.mock_hosts

    def get_links(self):
        """Get all links from mock ONOS"""
        return self.mock_links

    def get_switches(self):
        """Get all switch device IDs from mock ONOS"""
        return self.mock_switches

    def push_intent(self, ingress_point, egress_point):
        """Push host-to-host intent to mock ONOS"""
        return 200, "Mock intent created successfully"

    def push_flow(self, switch_id, output_port, priority, eth_type=None, eth_dst=None, eth_src=None, in_port=None):
        """Send a flow rule to mock ONOS"""
        flow = {
            "id": str(self.flow_id_counter),
            "appId": self.APP_ID,
            "priority": priority,
            "timeout": 0,
            "isPermanent": True,
            "deviceId": switch_id,
            "treatment": {
                "instructions": [{"type": "OUTPUT", "port": output_port}]
            },
            "selector": {"criteria": []},
            "state": "ADDED"
        }
        
        if in_port:
            flow["selector"]["criteria"].append({"type": "IN_PORT", "port": in_port})
        if eth_src:
            flow["selector"]["criteria"].append({"type": "ETH_SRC", "mac": eth_src})
        if eth_dst:
            flow["selector"]["criteria"].append({"type": "ETH_DST", "mac": eth_dst})
        if eth_type:
            flow["selector"]["criteria"].append({"type": "ETH_TYPE", "ethType": eth_type})
        
        if switch_id not in self.mock_flows:
            self.mock_flows[switch_id] = []
        self.mock_flows[switch_id].append(flow)
        
        self.flow_id_counter += 1
        return 200, "Mock flow created successfully"

    def push_flows_batch(self, flows_data):
        """Send multiple flows in a single batch request to mock ONOS"""
        if not flows_data:
            return []
        
        results = []
        for flow_data in flows_data:
            status, message = self.push_flow(
                flow_data['switch_id'],
                flow_data['output_port'], 
                flow_data['priority'],
                flow_data.get('eth_type'),
                flow_data.get('eth_dst'),
                flow_data.get('eth_src'),
                flow_data.get('in_port')
            )
            results.append((status, message))
        
        return results

    def delete_flows_batch(self, flows_to_delete):
        """Delete multiple flows in batch from mock ONOS"""
        if not flows_to_delete:
            return 200, "No flows to delete"
        
        deleted_count = 0
        for flow_info in flows_to_delete:
            device_id = flow_info['device_id']
            flow_id = flow_info['flow_id']
            
            if device_id in self.mock_flows:
                self.mock_flows[device_id] = [
                    f for f in self.mock_flows[device_id] 
                    if f['id'] != flow_id
                ]
                deleted_count += 1
        
        return 200, f"Deleted {deleted_count} flows"

    def get_topology(self):
        """Get topology information from mock ONOS"""
        return {
            "time": int(time.time() * 1000),
            "devices": len(self.mock_switches),
            "links": len(self.mock_links),
            "clusters": 1,
            "pathCount": len(self.mock_switches) * (len(self.mock_switches) - 1)
        }

    def get_port_statistics(self, device_id):
        """Get port statistics for a specific device from mock ONOS"""
        ports = []
        for i in range(1, 25):
            ports.append({
                "port": str(i),
                "packetsReceived": random.randint(1000, 10000),
                "packetsSent": random.randint(1000, 10000),
                "bytesReceived": random.randint(100000, 1000000),
                "bytesSent": random.randint(100000, 1000000),
                "packetsRxDropped": random.randint(0, 100),
                "packetsTxDropped": random.randint(0, 100),
                "packetsRxErrors": random.randint(0, 10),
                "packetsTxErrors": random.randint(0, 10),
                "durationSec": random.randint(100, 1000)
            })
        
        return {"statistics": ports}

    def get_metrics(self):
        """Get mock ONOS metrics"""
        return {
            "metrics": {
                "timer.onos.core.packetIn": {
                    "count": random.randint(1000, 10000),
                    "mean": random.uniform(1.0, 10.0)
                },
                "meter.onos.core.flowMod": {
                    "count": len([f for flows in self.mock_flows.values() for f in flows]),
                    "rate": random.uniform(10.0, 100.0)
                }
            }
        }

    def get_flows(self):
        """Get all flows from all devices in mock ONOS"""
        all_flows = []
        for device_flows in self.mock_flows.values():
            all_flows.extend(device_flows)
        
        return {"flows": all_flows}

    def delete_all_flows(self, batch_size=1000):
        """Delete all flows from all devices in mock ONOS"""
        total_deleted = 0
        
        for device_id in list(self.mock_flows.keys()):
            device_flows = self.mock_flows.get(device_id, [])
            core_flows = [f for f in device_flows if f.get('appId') == 'org.onosproject.core']
            deleted_count = len(device_flows) - len(core_flows)
            
            self.mock_flows[device_id] = core_flows
            total_deleted += deleted_count
        

    def delete_inactive_devices(self):
        """Delete inactive devices from mock ONOS (no-op for mock)"""

    def update_from_network_mock(self, network_mock):
        """Update data based on active network mock (simplified version)"""
        if not network_mock:
            return
        self._load_topology_data()

def main():
    """Test mock ONOS API"""
    api = OnosApiMock()
    print("Mock ONOS API methods:")
    methods = [method for method in dir(api) if not method.startswith('_') and callable(getattr(api, method))]
    for method in methods:
        print(f"  {method}")
    
    print(f"\nMock data loaded:")
    print(f"  Hosts: {len(api.get_hosts())}")
    print(f"  Switches: {len(api.get_switches())}")
    print(f"  Links: {len(api.get_links())}")

if __name__ == "__main__":
    main()