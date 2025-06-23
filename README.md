# MININET A* PARALLEL

Network routing solution using A* algorithm with Mininet, ONOS controller, and parallel processing optimization.

## Features

- **Parallel A* routing** with ProcessPoolExecutor
- **Geographic distance heuristics** using real topology data
- **ONOS controller integration** for SDN flow management
- **Network topology visualization** from GML files
- **Cross-platform compatibility** (Linux/Windows)

## Requirements

- Python 3.x
- ONOS Controller
- Mininet

Dependencies:
```
networkx
matplotlib
requests
python-dotenv
concurrent.futures
```

## Installation

1. Clone repository:
   ```bash
   git clone https://github.com/wilkertl/MININET_A-_PARALLEL
   cd MININET_A-_PARALLEL
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your ONOS settings
   ```

## Usage

### Main Application

Run the interactive application:

```bash
python src/app.py
```

Available commands:
- `simple_net` - Create simple 2-host topology
- `tower_net` - Create spine-leaf topology (configurable)
- `gml_net` - Load topology from brasil.gml
- `create_routes` - Install routes (sequential A*)
- `create_routes_parallel` - Install routes (parallel A*)
- `delete_routes` - Remove all flows
- `render_topology` - Generate topology visualization
- `ping_random` - Test connectivity between random hosts
- `ping_all` - Test full connectivity
- `traffic` - Generate dummy traffic
- `clean_network` - Clean Mininet and flows
- `help` - Show all commands
- `exit` - Exit application

### Direct Router Usage

```python
from router import Router

router = Router()
router.update()  # Get topology from ONOS
router.install_all_routes(parallel=True)
```

### Topology Visualization

```bash
python src/render_topology.py [gml_file] --output network.png
```

### ONOS API Management

```python
from onos_api import OnosApi

api = OnosApi()
hosts = api.get_hosts()
api.delete_all_flows()
```

## Configuration

Environment variables in `.env`:

```bash
ONOS_IP=127.0.0.1
ONOS_PORT=8181
ONOS_USER=onos
ONOS_PASSWORD=rocks
CONTROLERS=172.17.0.2
```

## Architecture

- **Precomputation**: Dijkstra all-pairs for switch distances
- **Route Processing**: Parallel A* with ProcessPoolExecutor
- **Heuristic**: O(1) lookup using precomputed distances
- **Batch Processing**: 1000 pairs/batch, 16 workers
- **Flow Installation**: Sequential HTTP requests to ONOS

## Project Structure

```
src/
├── app.py              # Main interactive application
├── router.py           # Parallel A* routing engine
├── network.py          # Mininet topology definitions
├── onos_api.py         # ONOS controller API
├── render_topology.py  # Network visualization
├── brasil.gml          # Brazil topology data
└── topology_data.json  # Distance/bandwidth cache
```

## License

MIT License 