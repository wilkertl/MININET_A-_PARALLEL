import requests
from requests.auth import HTTPBasicAuth

class OnosApi():
    def __init__(self, onos_ip, port):
        self.BASE_URL = f"http://{onos_ip}:{port}/onos/v1"  # <-- Replace <onos-ip>
        self.AUTH = HTTPBasicAuth("onos", "rocks")
        self.APP_ID = "org.onosproject.cli"  # or your own registered app name

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
        switches = [device['id'] for device in devices if device["type"] == "SWITCH"]
        return switches

    def push_intent(self, ingress_point, egress_point):
        data = {
            "type": "HostToHostIntent",
            "appId": APP_ID,
            "priority": 100,
            "one": f"{ingress_point}/-1",
            "two": f"{egress_point}/-1"
        }
        r = requests.post(f"{self.BASE_URL}/intents", json=data, auth=self.AUTH)
        return r.status_code, r.text

    def push_flow(self, device_id, eth_dst, out_port):
        """
        Pushes a flow rule to ONOS to forward packets with a given ETH_DST
        out a specified port on a specific switch.

        Args:
            device_id (str): The OpenFlow device ID (e.g., "of:0000000000000001")
            eth_dst (str): Destination MAC address to match (e.g., "00:00:00:00:00:A1:")
            out_port (str): Port to send the packet out (e.g., "2")
        """
        url = f"{self.BASE_URL}/flows/{device_id}"
        flow = {
            "priority": 40000,
            "timeout": 0,
            "isPermanent": True,
            "deviceId": device_id,
            "treatment": {
                "instructions": [{
                    "type": "OUTPUT",
                    "port": out_port
                }]
            },
            "selector": {
                "criteria": [{
                            "type": "ETH_DST",
                            "mac": eth_dst
                }]
            }
        }

        response = requests.post(
            url,
            auth=self.AUTH,
            json=flow
        )

        return response.status_code, response.text

    def get_topology():
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

def main():
    #push_flow("of:000000000000000d", "00:00:00:00:00:03", "2")
    print(get_topology())
    print()
    metrics = get_metrics()["metrics"]
    print(metrics[0])
    print()
    print(metrics[1])
    print()
    ports = get_port_statistics("of:000000000000000d")["statistics"][0]["ports"]
    print(ports[0])

if __name__ == "__main__":
    main()

