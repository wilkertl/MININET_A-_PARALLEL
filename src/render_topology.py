import os
import sys
import random
import networkx as nx
import matplotlib.pyplot as plt
import math

# Project configurations
MIN_BACKBONE_BW_MBPS = 30.0  
MAX_BACKBONE_BW_MBPS = 100.0  
EDGE_SWITCH_DEGREE_THRESHOLD = 2  
LOW_LINK_CHANCE = 0.30 
HOST_BW_MBPS = 10.0

# Visualization configurations
DEFAULT_GML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'brasil.gml')
FIGURE_SIZE = (20, 15)
NODE_SIZE_RANGE = (20, 300)
EDGE_WIDTH_RANGE = (0.2, 3.0)
FONT_SIZE = 8

def make_dpid(index):
    """Generate a 16-digit hexadecimal formatted DPID"""
    return format(index, '016x')

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate geodesic distance in km"""
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def classify_nodes(G):
    """Classify nodes as edge or backbone switches based on degree threshold"""
    edge_nodes = []
    backbone_nodes = []
    
    for node_id in G.nodes():
        node_degree = G.degree(node_id)
        if node_degree <= EDGE_SWITCH_DEGREE_THRESHOLD:
            edge_nodes.append(node_id)
        else:
            backbone_nodes.append(node_id)
    
    return edge_nodes, backbone_nodes

def assign_bandwidth_to_edges(G):
    """Assign bandwidth to edges using project logic"""
    for u, v, data in G.edges(data=True):
        if 'bandwidth' not in data:
            if random.uniform(0, 1) < LOW_LINK_CHANCE:
                data['bandwidth'] = MIN_BACKBONE_BW_MBPS
            else:
                data['bandwidth'] = MAX_BACKBONE_BW_MBPS

def calculate_node_metrics(G):
    """Calculate node capacity and classify nodes for visualization"""
    edge_nodes, backbone_nodes = classify_nodes(G)
    
    node_capacity = {node: 0 for node in G.nodes()}
    for u, v, data in G.edges(data=True):
        bw = data.get('bandwidth', 0)
        node_capacity[u] += bw
        node_capacity[v] += bw
    
    return node_capacity, edge_nodes, backbone_nodes

def get_node_positions(G):
    """Extract geographic positions from GML data"""
    pos = {}
    for node, data in G.nodes(data=True):
        lat = data.get('lat', data.get('Latitude', 0.0))
        lon = data.get('lon', data.get('Longitude', 0.0))
        pos[node] = (lon, lat)
    
    return pos

def visualize_topology(G, output_filename="topology_visualization.png", show_plot=True):
    """Render topology with enhanced visualization showing node classification and bandwidth"""
    print(f"Generating topology visualization in '{output_filename}'...")
    
    assign_bandwidth_to_edges(G)
    pos = get_node_positions(G)
    node_capacity, edge_nodes, backbone_nodes = calculate_node_metrics(G)
    
    if max(node_capacity.values(), default=0) > 0:
        max_cap = max(node_capacity.values())
        node_sizes = {
            node: NODE_SIZE_RANGE[0] + (node_capacity[node] / max_cap) * (NODE_SIZE_RANGE[1] - NODE_SIZE_RANGE[0])
            for node in G.nodes()
        }
    else:
        node_sizes = {node: 50 for node in G.nodes()}
    
    edge_widths = []
    max_bw = max([data.get('bandwidth', 0) for u, v, data in G.edges(data=True)], default=1)
    for u, v, data in G.edges(data=True):
        bw = data.get('bandwidth', 0)
        width = EDGE_WIDTH_RANGE[0] + (bw / max_bw) * (EDGE_WIDTH_RANGE[1] - EDGE_WIDTH_RANGE[0])
        edge_widths.append(width)
    
    plt.figure(figsize=FIGURE_SIZE)
    
    nx.draw_networkx_edges(G, pos, width=edge_widths, edge_color='gray', alpha=0.6)
    
    if edge_nodes:
        edge_sizes = [node_sizes[node] for node in edge_nodes]
        nx.draw_networkx_nodes(G, pos, nodelist=edge_nodes, 
                              node_size=edge_sizes, node_color='lightblue', 
                              alpha=0.8, edgecolors='navy', linewidths=1)
    
    if backbone_nodes:
        backbone_sizes = [node_sizes[node] for node in backbone_nodes]
        nx.draw_networkx_nodes(G, pos, nodelist=backbone_nodes,
                              node_size=backbone_sizes, node_color='lightcoral',
                              alpha=0.8, edgecolors='darkred', linewidths=2)
    
    nx.draw_networkx_labels(G, pos, font_size=FONT_SIZE, font_weight='bold')
    
    plt.title(f"Network Topology Visualization\nEdge Switches: {len(edge_nodes)} | Backbone Switches: {len(backbone_nodes)}", 
              size=16, fontweight='bold', pad=20)
    plt.xlabel("Longitude", size=12)
    plt.ylabel("Latitude", size=12)
    plt.grid(True, linestyle='--', alpha=0.4)
    
    plt.gca().set_aspect('equal', adjustable='box')
    
    all_longitudes = [lon for lon, lat in pos.values() if lon is not None]
    all_latitudes = [lat for lon, lat in pos.values() if lat is not None]
    
    if all_longitudes and all_latitudes:
        lon_min, lon_max = min(all_longitudes), max(all_longitudes)
        lat_min, lat_max = min(all_latitudes), max(all_latitudes)
        
        lon_range = lon_max - lon_min
        lat_range = lat_max - lat_min
        padding_lon = lon_range * 0.1 if lon_range > 0 else 1
        padding_lat = lat_range * 0.1 if lat_range > 0 else 1
        
        plt.xlim(lon_min - padding_lon, lon_max + padding_lon)
        plt.ylim(lat_min - padding_lat, lat_max + padding_lat)
    
    legend_elements = [
        plt.scatter([], [], c='lightblue', s=100, edgecolors='navy', label='Edge Switches'),
        plt.scatter([], [], c='lightcoral', s=100, edgecolors='darkred', label='Backbone Switches')
    ]
    plt.legend(handles=legend_elements, loc='upper right')
    
    plt.tight_layout()
    
    try:
        plt.savefig(output_filename, format="PNG", dpi=300, bbox_inches='tight')
        print(f"Visualization successfully saved to '{output_filename}'.")
        
        print(f"Topology Statistics:")
        print(f"  - Total nodes: {len(G.nodes())}")
        print(f"  - Total edges: {len(G.edges())}")
        print(f"  - Edge switches: {len(edge_nodes)}")
        print(f"  - Backbone switches: {len(backbone_nodes)}")
        
        if show_plot:
            plt.show()
        else:
            plt.close()
            
    except Exception as e:
        print(f"An error occurred while saving the visualization: {e}")
        return False
    
    return True

def load_gml_topology(gml_file):
    """Load GML topology file"""
    if not os.path.exists(gml_file):
        print(f"Error: GML file '{gml_file}' not found.")
        return None
    
    print(f"Reading topology from GML file: {gml_file}")
    
    try:
        G = nx.read_gml(gml_file, label='id')
        print(f"Successfully loaded topology with 'id' labels.")
    except Exception as e:
        print(f"Error reading GML file with label='id' ({e}). Trying 'label'...")
        try:
            G = nx.read_gml(gml_file, label='label')
            print(f"Successfully loaded topology with 'label' labels.")
        except Exception as e2:
            print(f"Final error reading GML file ({e2}). Check file format.")
            return None
    
    return G

def render_topology(gml_file=DEFAULT_GML_FILE, output_filename="topology_visualization.png", show_plot=False):
    """Render topology with enhanced visualization showing node classification and bandwidth"""
    G = load_gml_topology(gml_file)
    if G is None:
        return 1
    
    success = visualize_topology(G, output_filename, show_plot=not show_plot)
    
    if success:
        print("\nTopology visualization completed successfully.")
        return 0
    else:
        print("\nTopology visualization failed.")
        return 1

def main():
    """Main function to orchestrate topology loading and visualization"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Visualize network topology from GML file')
    parser.add_argument('gml_file', nargs='?', default=DEFAULT_GML_FILE,
                       help=f'Path to GML file (default: {DEFAULT_GML_FILE})')
    parser.add_argument('--output', '-o', default='topology_visualization.png',
                       help='Output filename for visualization (default: topology_visualization.png)')
    parser.add_argument('--no-show', action='store_true',
                       help='Don\'t display the plot window')
    
    args = parser.parse_args()
    
    render_topology(args.gml_file, args.output, show_plot=not args.no_show)

if __name__ == '__main__':
    exit(main())