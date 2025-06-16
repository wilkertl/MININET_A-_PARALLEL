import requests
from requests.auth import HTTPBasicAuth

BASE_URL = "http://192.168.56.101:7001/onos/v1"  # <-- Replace <onos-ip>
AUTH = HTTPBasicAuth("onos", "rocks")
APP_ID = "org.onosproject.cli"  # or your own registered app name

def get_hosts():
    r = requests.get(f"{BASE_URL}/hosts", auth=AUTH)
    r.raise_for_status()
    return r.json()["hosts"]

def get_links():
    r = requests.get(f"{BASE_URL}/links", auth=AUTH)
    r.raise_for_status()
    return r.json()["links"]

def get_switches():
    url = f"{BASE_URL}/devices"
    response = requests.get(url, auth=AUTH)
    response.raise_for_status()
    devices = response.json().get("devices", [])
    switches = [device['id'] for device in devices if device["type"] == "SWITCH"]
    return switches

def push_intent(ingress_point, egress_point):
    data = {
        "type": "HostToHostIntent",
        "appId": APP_ID,
        "priority": 100,
        "one": f"{ingress_point}/-1",
        "two": f"{egress_point}/-1"
    }
    r = requests.post(f"{BASE_URL}/intents", json=data, auth=AUTH)
    return r.status_code, r.text

def push_flow(device_id, eth_dst, out_port):
    """
    Pushes a flow rule to ONOS to forward packets with a given ETH_DST
    out a specified port on a specific switch.

    Args:
        device_id (str): The OpenFlow device ID (e.g., "of:0000000000000001")
        eth_dst (str): Destination MAC address to match (e.g., "00:00:00:00:00:A1:")
        out_port (str): Port to send the packet out (e.g., "2")
    """
    url = f"{BASE_URL}/flows/{device_id}"
    flow = {
        "priority": 40000,
        "timeout": 0,
        "isPermanent": True,
        "deviceId": device_id,
        "treatment": {
            "instructions": [
                {
                    "type": "OUTPUT",
                    "port": out_port
                }
            ]
        },
        "selector": {
            "criteria": [
                {
                    "type": "ETH_DST",
                    "mac": eth_dst
                }
            ]
        }
    }

    response = requests.post(
        url,
        auth=AUTH,
        json=flow
    )

    return response.status_code, response.text

def main():
    push_flow("of:000000000000000d", "00:00:00:00:00:03", "2")

if __name__ == "__main__":
    main()

