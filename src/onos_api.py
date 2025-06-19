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
            "appId": self.APP_ID,
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
        # Get all devices with flow rules
        get_url = f"{self.BASE_URL}/flows"
        response = requests.get(get_url, auth=self.AUTH)
        if response.status_code != 200:
            print("Failed to fetch flows:", response.status_code, response.text)
            return

        data = response.json()
        flows = data.get('flows', [])

        # Extract unique deviceIds

        # Delete all flows per device
        for flow in flows:
            print(flow)
            device_id = flow['deviceId']
            flow_id = flow['id']
            del_url = f'{self.BASE_URL}/{device_id}/{flow_id}'
            del_resp = requests.delete(del_url, auth=self.AUTH)
            if del_resp.status_code in (204, 200):
                print(f"Deleted all flows on {device_id}")
            else:
                print(f"Failed to delete flow {flow_id} on {device_id}: {del_resp.status_code}")
                return

        print("Flow deletion complete.")


    def delete_inactive_devices(self):
        url = f"{self.BASE_URL}/devices"

        resp = requests.get(url, auth=self.AUTH)
        devices = resp.json().get("devices", [])

        for dev in devices:
            if not dev.get("available", False):  # INACTIVE
                dev_id = dev["id"]
                del_url = f"{url}/{dev_id}"
                del_resp = requests.delete(del_url, auth=self.AUTH)
                if del_resp.status_code in (200, 204):
                    print(f"Deleted inactive device: {dev_id}")
                else:
                    print(f"Could not delete device {dev_id}: {del_resp.status_code}")

def main():
    api = OnosApi("192.168.56.101", 7001)
    #push_flow("of:000000000000000d", "00:00:00:00:00:03", "2")
    # print(api.get_topology())
    # print()
    # metrics = api.get_metrics()["metrics"]
    # print(metrics[0])
    # print()
    # print(metrics[1])
    # print()
    # ports = api.get_port_statistics("of:000000000000000d")["statistics"][0]["ports"]
    # print(ports[0])
    #api.delete_all_flows()
    api.delete_inactive_devices()

if __name__ == "__main__":
    main()

