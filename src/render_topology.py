#!/usr/bin/python3
"""
Este script baixa e renderiza uma topologia de rede do repositório
Topohub usando NetworkX e Matplotlib.

Versão Corrigida: Lê as coordenadas 'lon' e 'lat' corretamente
do arquivo GML para gerar uma visualização geográfica precisa.
"""

import os
import random
import re
import networkx as nx
import matplotlib.pyplot as plt

# --- CONFIGURAÇÕES GLOBAIS ---
TOPOLOGY_FILE_URL = 'https://raw.githubusercontent.com/TopoHub/topologies/master/tata_nld.gml'
MAX_BACKBONE_BW_GBPS = 10.0

# --- FIM DAS CONFIGURAÇÕES ---

def visualize_topology(G, output_filename="topology_visualization.png"):
    """
    Renderiza a topologia de forma rica e informativa, usando o layout
    geográfico baseado nas coordenadas 'lon' e 'lat' do arquivo.
    """
    print(f"Gerando a visualização da topologia em '{output_filename}'...")

    # 1. Posição dos nós (layout geográfico)
    # CORREÇÃO: Usar 'lon' e 'lat' (minúsculas) para corresponder ao arquivo GML.
    pos = {node: (data.get('lon', 0.0), data.get('lat', 0.0))
           for node, data in G.nodes(data=True)}

    # 2. Tamanho dos nós (proporcional à capacidade total de banda)
    # Atribui banda aleatória para fins de visualização
    for u, v, data in G.edges(data=True):
        data['bandwidth'] = random.uniform(100.0, MAX_BACKBONE_BW_GBPS * 1000)

    node_capacity = {node: 0 for node in G.nodes()}
    for u, v, data in G.edges(data=True):
        bw = data.get('bandwidth', 0)
        node_capacity[u] += bw
        node_capacity[v] += bw
    
    if max(node_capacity.values(), default=0) > 0:
        max_cap = max(node_capacity.values())
        node_sizes = [20 + (node_capacity[node] / max_cap) * 250 for node in G.nodes()]
    else:
        node_sizes = [30 for node in G.nodes()]

    # 3. Espessura das arestas
    edge_widths = [0.2 + (data.get('bandwidth', 0) / (MAX_BACKBONE_BW_GBPS * 1000)) * 1.5
                   for u, v, data in G.edges(data=True)]

    # Criação da figura para o plot
    plt.figure(figsize=(20, 15))
    
    # Desenha os componentes do grafo
    nx.draw_networkx_edges(G, pos, width=edge_widths, edge_color='gray', alpha=0.6)
    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color='skyblue', alpha=0.9, edgecolors='white')
    nx.draw_networkx_labels(G, pos, font_size=8, font_weight='bold')

    # Configurações do gráfico
    plt.title(f"Visualização da Topologia: {os.path.basename(TOPOLOGY_FILE_URL)}", size=24, fontweight='bold', pad=20)
    plt.xlabel("Longitude", size=12)
    plt.ylabel("Latitude", size=12)
    plt.grid(True, linestyle='--', alpha=0.4)
    
    # Força a proporção correta dos eixos
    plt.gca().set_aspect('equal', adjustable='box')

    # --- CÁLCULO E AJUSTE AUTOMÁTICO DOS LIMITES (ZOOM) ---
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
    
    plt.tight_layout()

    # Salva e exibe a imagem
    try:
        plt.savefig(output_filename, format="PNG", dpi=300)
        print(f"Visualização salva com sucesso em '{output_filename}'.")
        plt.show()
    except Exception as e:
        print(f"Ocorreu um erro ao salvar ou exibir o gráfico: {e}")

def main():
    """
    Função principal para orquestrar o download, processamento e visualização.
    """
    file_name = TOPOLOGY_FILE_URL.split('/')[-1]
    if not os.path.exists(file_name):
        print(f"Baixando o arquivo da topologia: {file_name}...")
        os.system(f"wget {TOPOLOGY_FILE_URL}")

    print("Lendo e processando a topologia do arquivo GML...")
    G = None
    try:
        # A maioria dos GMLs usa 'id' como um inteiro para o nó
        G = nx.read_gml(file_name, label='id')
    except Exception as e:
        print(f"Erro ao ler o arquivo GML com label='id' ({e}). Tentando outras opções...")
        try:
             # Fallback para 'label' como string
             G = nx.read_gml(file_name, label='label')
        except Exception as e2:
             print(f"Erro final ao ler o arquivo GML ({e2}). Verifique o formato do arquivo.")
             return

    visualize_topology(G)
    print("\nProcesso de renderização concluído.")


if __name__ == '__main__':
    main()