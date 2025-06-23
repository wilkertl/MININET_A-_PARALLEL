import requests
import json
from requests.auth import HTTPBasicAuth
import os
from dotenv import load_dotenv

load_dotenv()

class OnosApi():
    def __init__(self, onos_ip=None, port=None, username=None, password=None):
        self.onos_ip = onos_ip or os.getenv('ONOS_IP', '127.0.0.1')
        self.port = port or os.getenv('ONOS_PORT', '8181')
        self.username = username or os.getenv('ONOS_USER', 'onos')
        self.password = password or os.getenv('ONOS_PASSWORD', 'rocks')
        
        self.BASE_URL = f"http://{self.onos_ip}:{self.port}/onos/v1"
        self.AUTH = HTTPBasicAuth(self.username, self.password)
        self.APP_ID = "org.onosproject.cli"
        
    def get_hosts(self):
        """Get all hosts from ONOS"""
        r = requests.get(f"{self.BASE_URL}/hosts", auth=self.AUTH)
        r.raise_for_status()
        return r.json()["hosts"]

    def get_links(self):
        """Get all links from ONOS"""
        r = requests.get(f"{self.BASE_URL}/links", auth=self.AUTH)
        r.raise_for_status()
        return r.json()["links"]

    def get_switches(self):
        """Get all switch device IDs from ONOS"""
        url = f"{self.BASE_URL}/devices"
        response = requests.get(url, auth=self.AUTH)
        response.raise_for_status()
        devices = response.json().get("devices", [])
        return [device['id'] for device in devices if device["type"] == "SWITCH"]

    def push_intent(self, ingress_point, egress_point):
        """Push host-to-host intent to ONOS"""
        data = {
            "type": "HostToHostIntent",
            "appId": self.APP_ID,
            "priority": 100,
            "one": f"{ingress_point}/-1",
            "two": f"{egress_point}/-1"
        }
        r = requests.post(f"{self.BASE_URL}/intents", json=data, auth=self.AUTH)
        return r.status_code, r.text

    def push_flow(self, switch_id, output_port, priority, eth_type=None, eth_dst=None, eth_src=None, in_port=None):
        """Send a flow rule to a specific device in ONOS"""
        try:
            url = f"{self.BASE_URL}/flows/{switch_id}"

            criteria = []
            if in_port:
                criteria.append({"type": "IN_PORT", "port": in_port})
            if eth_src:
                criteria.append({"type": "ETH_SRC", "mac": eth_src})
            if eth_dst:
                criteria.append({"type": "ETH_DST", "mac": eth_dst})
            if eth_type:
                criteria.append({"type": "ETH_TYPE", "ethType": eth_type})

            flow_data = {
                "priority": priority,
                "isPermanent": True,
                "deviceId": switch_id,
                "treatment": {
                    "instructions": [{"type": "OUTPUT", "port": output_port}]
                },
                "selector": {"criteria": criteria}
            }

            response = requests.post(
                url,
                auth=self.AUTH,
                data=json.dumps(flow_data),
                headers={'Content-Type': 'application/json', 'Accept': 'application/json'}
            )

            return response.status_code, response.text
        except Exception as e:
            print(f"Error sending flow: {e}")
            return 500, f"Error: {e}"
    
    def push_flows_batch(self, flows_data):
        """Send multiple flows in a single batch request"""
        if not flows_data:
            return []
        
        batch_flows = []
        for flow in flows_data:
            criteria = []
            if flow.get('in_port'):
                criteria.append({"type": "IN_PORT", "port": flow['in_port']})
            if flow.get('eth_src'):
                criteria.append({"type": "ETH_SRC", "mac": flow['eth_src']})
            if flow.get('eth_dst'):
                criteria.append({"type": "ETH_DST", "mac": flow['eth_dst']})
            if flow.get('eth_type'):
                criteria.append({"type": "ETH_TYPE", "ethType": flow['eth_type']})

            flow_data = {
                "priority": flow['priority'],
                "timeout": 40000,
                "isPermanent": flow.get('isPermanent', True),
                "deviceId": flow['switch_id'],
                "treatment": {
                    "instructions": [{"type": "OUTPUT", "port": flow['output_port']}]
                },
                "selector": {"criteria": criteria}
            }
            batch_flows.append(flow_data)

        try:
            url = f"{self.BASE_URL}/flows"
            payload = {"flows": batch_flows}
            
            response = requests.post(
                url,
                auth=self.AUTH,
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json', 'Accept': 'application/json'}
            )
            
            if response.status_code in [200, 201]:
                return [(200, "Success")] * len(flows_data)
            else:
                print(f"Batch flow creation failed ({response.status_code}): {response.text[:100]}")
                return [(response.status_code, response.text)] * len(flows_data)
                
        except Exception as e:
            print(f"Error sending batch flows: {e}")
            return [(500, f"Error: {e}")] * len(flows_data)
    
    def delete_flows_batch(self, flows_to_delete):
        """Delete multiple flows in batch using ONOS batch endpoint"""
        if not flows_to_delete:
            return 200, "No flows to delete"
            
        flows_list = [
            {"deviceId": flow['device_id'], "flowId": flow['flow_id']}
            for flow in flows_to_delete
        ]
        
        payload = {"flows": flows_list}
        
        try:
            del_url = f'{self.BASE_URL}/flows'
            response = requests.delete(
                del_url, 
                auth=self.AUTH,
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'}
            )
            return response.status_code, response.text
        except Exception as e:
            return 500, f"Error: {e}"

    def get_topology(self):
        """Get topology information from ONOS"""
        url = f"{self.BASE_URL}/topology"
        response = requests.get(url, auth=self.AUTH)
        return response.json()

    def get_port_statistics(self, device_id):
        """Get port statistics for a specific device"""
        url = f"{self.BASE_URL}/statistics/ports/{device_id}"
        response = requests.get(url, auth=self.AUTH)
        return response.json()

    def get_metrics(self):
        """Get ONOS metrics"""
        url = f"{self.BASE_URL}/metrics"
        response = requests.get(url, auth=self.AUTH)
        return response.json()

    def get_flows(self):
        """Get all flows from all devices"""
        devices = self.get_switches()
        all_flows = []
        
        for device_id in devices:
            try:
                device_url = f"{self.BASE_URL}/flows/{device_id}"
                response = requests.get(device_url, auth=self.AUTH)
                
                if response.status_code == 200:
                    data = response.json()
                    flows = data.get('flows', [])
                    all_flows.extend(flows)
            except Exception as e:
                print(f"Error getting flows for {device_id}: {e}")
                continue
        
        return {"flows": all_flows}

    def delete_all_flows(self, batch_size=1000):
        """Delete all flows from all devices"""
        devices = self.get_switches()
        if not devices:
            return

        total_deleted = 0
        
        for i, device_id in enumerate(devices):
            device_url = f"{self.BASE_URL}/flows/{device_id}"
            response = requests.get(device_url, auth=self.AUTH)
            
            if response.status_code != 200:
                print(f"Failed to fetch flows for {device_id}: {response.status_code}")
                continue

            data = response.json()
            flows = data.get('flows', [])

            flows_to_delete = []
            for flow in flows:
                if flow.get('appId') == 'org.onosproject.core':
                    continue
                    
                flows_to_delete.append({
                    'device_id': device_id,
                    'flow_id': flow['id']
                })

            if flows_to_delete:
                status, message = self.delete_flows_batch(flows_to_delete)
                if status not in [200, 204]:
                    pass
                else:
                    total_deleted += len(flows_to_delete)

    def delete_inactive_devices(self):
        """Delete inactive devices from ONOS"""
        try:
            devices_url = f"{self.BASE_URL}/devices"
            response = requests.get(devices_url, auth=self.AUTH)
            devices = response.json().get('devices', [])
            
            for device in devices:
                if not device.get('available', True):
                    dev_id = device['id']
                    del_url = f"{devices_url}/{dev_id}"
                    del_resp = requests.delete(del_url, auth=self.AUTH)
                    
        except Exception:
            pass

def main():
    api = OnosApi()
    print("Available methods:")
    methods = [method for method in dir(api) if not method.startswith('_') and callable(getattr(api, method))]
    for method in methods:
        print(f"  {method}")

if __name__ == "__main__":
    main()

