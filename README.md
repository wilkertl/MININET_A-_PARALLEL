# MININET A* PARALLEL

This project implements an A* algorithm-based routing solution for network topologies using Mininet, ONOS controller, and Python visualization tools.

## Description

The project provides:
- **A* routing algorithm** with real geographic distance heuristics
- **Network topology visualization** from GML files
- **ONOS controller integration** for SDN flow management
- **Cross-platform compatibility** (Linux/Windows)

Key features:
- Nodes represent switches and hosts with geographic coordinates
- Edges show bandwidth-based connections
- Classification between edge switches (blue) and backbone switches (red)
- Real-time topology updates via ONOS API

## Requirements

- Python 3.x
- Python dependencies:
  ```
  networkx
  matplotlib
  requests
  python-dotenv
  ```

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/wilkertl/MININET_A-_PARALLEL
   cd MININET_A-_PARALLEL
   ```

2. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # or
   .venv\Scripts\activate  # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env file with your ONOS controller settings
   ```

## Configuration

The project uses environment variables for configuration. Copy `.env.example` to `.env` and adjust the values:

```bash
# ONOS Controller Configuration
ONOS_IP=127.0.0.1
ONOS_PORT=8181
ONOS_USER=onos
ONOS_PASSWORD=rocks

# Mininet Controllers (comma-separated list)
CONTROLERS=172.17.0.2
```

## Usage

### Network Visualization

Visualize network topology from GML files:

```bash
python src/render_topology.py [gml_file]
```

Examples:
```bash
# Use default GML file (brasil.gml)
python src/render_topology.py

# Custom GML file and output
python src/render_topology.py custom_topology.gml --output my_network.png

# Generate without showing plot window
python src/render_topology.py --no-show
```

### A* Routing

Run the A* routing algorithm with ONOS:

```bash
python src/router.py
```

The router will:
- Load topology data from `topology_data.json`
- Connect to ONOS controller (default: localhost:8181)
- Calculate optimal paths using A* with geographic heuristics
- Install flows in the network

## Project Structure

```
MININET_A-_PARALLEL/
├── src/
│   ├── router.py           # A* routing implementation
│   ├── network.py          # Mininet topology setup
│   ├── app.py              # Network management utilities
│   ├── onos_api.py         # ONOS controller API
│   ├── render_topology.py  # Topology visualization
│   ├── brasil.gml          # Brazil topology data
│   └── topology_data.json  # Distance/bandwidth data
├── .env.example            # Environment variables template
├── requirements.txt        # Python dependencies
└── README.md
```

## Contributing

1. Fork the project
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit changes (`git commit -m 'Add new feature'`)
4. Push to branch (`git push origin feature/new-feature`)
5. Open a Pull Request

## License

This project is under the MIT license. 