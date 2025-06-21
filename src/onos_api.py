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
        r = requests.get(f"{self.BASE_URL}/hosts", auth=self.AUTH)
        r.raise_for_status()
        return r.json()["hosts"]

    def get_links(self):
        r = requests.get(f"{self.BASE_URL}/links", auth=self.AUTH)
        r.raise_for_status()
        return r.json()["links"]

    def get_switches(self):
        url = f"{self.BASE_URL}/devices"
        response = requests.get(url, auth=self.AUTH)
        response.raise_for_status()
        devices = response.json().get("devices", [])
        return [device['id'] for device in devices if device["type"] == "SWITCH"]

    def push_intent(self, ingress_point, egress_point):
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
        """Envia uma regra de fluxo para um dispositivo específico no ONOS"""
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
            print(f"Erro ao enviar flow: {e}")
            return 500, f"Erro: {e}"
    
    def push_flows_batch(self, flows_data):
        """Envia múltiplos flows em massa"""
        results = []
        created_count = 0
        for i, flow in enumerate(flows_data):
            status, msg = self.push_flow(
                flow['switch_id'],
                flow['output_port'], 
                flow['priority'],
                flow.get('eth_type'),
                flow.get('eth_dst'),
                flow.get('eth_src'),
                flow.get('in_port')
            )
            results.append((status, msg))
            
            if status == 201:
                created_count += 1
            elif status != 201:
                print(f"Flow {i+1} falhou ({status}): {msg[:100]}")
            
        print(f"✓ Flows processados: {created_count} criados com sucesso")
        return results
    
    def delete_flows_batch(self, flows_to_delete):
        """Deleta múltiplos flows em massa usando endpoint batch do ONOS"""
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
            return 500, f"Erro: {e}"

    def get_topology(self):
        url = f"{self.BASE_URL}/topology"
        response = requests.get(url, auth=self.AUTH)
        return response.json()

    def get_port_statistics(self, device_id):
        url = f"{self.BASE_URL}/statistics/ports/{device_id}"
        response = requests.get(url, auth=self.AUTH)
        return response.json()

    def get_metrics(self):
        url = f"{self.BASE_URL}/metrics"
        response = requests.get(url, auth=self.AUTH)
        return response.json()

    def delete_all_flows(self):
        get_url = f"{self.BASE_URL}/flows"
        response = requests.get(get_url, auth=self.AUTH)
        if response.status_code != 200:
            print("Failed to fetch flows:", response.status_code, response.text)
            return

        data = response.json()
        flows = data.get('flows', [])

        flows_to_delete = []
        for flow in flows:
            crit = flow.get('selector', {}).get('criteria', [])
            if any(c.get('type') == 'ETH_TYPE' and c.get('ethType') in ['lldp', '0x88cc', 'bddp'] for c in crit):
                continue
            flows_to_delete.append({
                'device_id': flow['deviceId'],
                'flow_id': flow['id']
            })

        if flows_to_delete:
            status, message = self.delete_flows_batch(flows_to_delete)
            if status in (200, 204):
                print(f"Flow deletion complete: {len(flows_to_delete)} flows deleted")
            else:
                print(f"Error deleting flows: {status} - {message}")
        else:
            print("No flows to delete")

    def delete_inactive_devices(self):
        url = f"{self.BASE_URL}/devices"
        resp = requests.get(url, auth=self.AUTH)
        devices = resp.json().get("devices", [])

        for dev in devices:
            if not dev.get("available", False):  
                dev_id = dev["id"]
                del_url = f"{url}/{dev_id}"
                del_resp = requests.delete(del_url, auth=self.AUTH)
                if del_resp.status_code in (200, 204):
                    print(f"Deleted inactive device: {dev_id}")
                else:
                    print(f"Could not delete device {dev_id}: {del_resp.status_code}")

def main():
    api = OnosApi()
    api.delete_all_flows()
    api.delete_inactive_devices()

if __name__ == "__main__":
    main()

