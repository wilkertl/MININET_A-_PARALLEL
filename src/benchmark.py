#!/usr/bin/env python3
"""
Benchmark comparing router implementations - simplified version
"""

import sys
import os
import time

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import router implementations
from router import Router
from router_dijkstra import RouterDijkstra

# Try to import PyCUDA router
try:
    from router_pycuda import RouterPyCUDA
    PYCUDA_AVAILABLE = True
except:
    PYCUDA_AVAILABLE = False

def benchmark_astar_router_sequential(topo_file) -> dict:
    """Test A* router (both sequential and parallel)"""
    print(f"\nA* Router:")
    
    try:
        router = Router(topo_file=topo_file)
        router.update()
        
        results = {
            'name': 'A* (CPU) Sequential',
        }
        
        # Sequential test
        try:
            start = time.time()
            flows_seq = router.install_all_routes(parallel=False)
            seq_time = time.time() - start
            results['time'] = seq_time
            results['flows'] = len(flows_seq)
            print(f"  Sequential: {len(flows_seq)} flows in {seq_time:.2f}s")
        except Exception as e:
            print(f"  Sequential: ERROR - {e}")
            results['sequential'] = None
            
        return results
        
    except Exception as e:
        print(f"  Initialization ERROR: {e}")
        return {'name': 'A* Router', 'error': str(e)}
    
def benchmark_astar_router_parallel(topo_file) -> dict:
    """Test A* router (both sequential and parallel)"""
    print(f"\nA* Router:")
    
    try:
        router = Router(topo_file=topo_file)
        router.update()
        
        results = {
            'name': 'A* (CPU) Parallel',
        }
        
        # Parallel test
        try:
            start = time.time()
            flows_par = router.install_all_routes(parallel=True)
            par_time = time.time() - start
            results['time'] = par_time
            results['flows'] = len(flows_par)
            print(f"  Parallel: {len(flows_par)} flows in {par_time:.2f}s")
        except Exception as e:
            print(f"  Parallel: ERROR - {e}")
            results['parallel'] = None
            
        return results
        
    except Exception as e:
        print(f"  Initialization ERROR: {e}")
        return {'name': 'A* Router', 'error': str(e)}

def benchmark_dijkstra_router(topo_file) -> dict:
    """Test Dijkstra router (parallel only)"""
    print(f"\nDijkstra Router:")
    
    try:
        router = RouterDijkstra(topo_file=topo_file)
        router.update()
        
        results = {
            'name': 'Dijkstra (CPU) ',
        }
        
        # Parallel test only
        try:
            start = time.time()
            flows = router.install_all_routes(parallel=True)
            par_time = time.time() - start
            results['time'] = par_time
            results['flows'] = len(flows)
            print(f"  Parallel: {len(flows)} flows in {par_time:.2f}s")
        except Exception as e:
            print(f"  Parallel: ERROR - {e}")
            results['parallel'] = None
            
        return results
        
    except Exception as e:
        print(f"  Initialization ERROR: {e}")
        return {'name': 'Dijkstra Router', 'error': str(e)}

def benchmark_pycuda_router(topo_file) -> dict:
    """Test PyCUDA router (GPU-accelerated only)"""
    print(f"\nPyCUDA Router:")
    
    try:
        router = RouterPyCUDA(topo_file=topo_file)
        router.update()
        
        results = {
            'name': 'Dijkstra (GPU) ',
        }
        
        # GPU-accelerated test only
        try:
            start = time.time()
            flows = router.install_all_routes()  # Always GPU-optimized
            gpu_time = time.time() - start
            results['time'] = gpu_time
            results['flows'] = len(flows)
            print(f"  GPU-accelerated: {len(flows)} flows in {gpu_time:.2f}s")
        except Exception as e:
            print(f"  GPU-accelerated: ERROR - {e}")
            results['gpu_accelerated'] = None
            
        return results
        
    except Exception as e:
        print(f"  Initialization ERROR: {e}")
        return {'name': 'PyCUDA Router', 'error': str(e)}

def full_test():
    tests = [benchmark_astar_router_sequential, benchmark_astar_router_parallel, benchmark_dijkstra_router]
    if PYCUDA_AVAILABLE:
        print("PyCUDA Router: AVAILABLE")
        tests.append(benchmark_pycuda_router)

    results  = []

    folder = "topologies/"
    files = [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]

    for file in files:
        r = {
            "file": file.split("/")[-1].split(".")[0],
            "data": []
        }

        for test in tests:
            r["data"].append(test(file))

        results.append(r)

    print(results[0])
    return results

import matplotlib.pyplot as plt
def generate_graphs(data):
    files = []
    x_num = []
    ys = {}

    for d in data:
        files.append(d["file"])

        for y in d["data"]:
            if y["name"] not in ys.keys():
                ys[y["name"]] = []

            ys[y["name"]].append(y["time"])

    width = 0.35

    os.makedirs('benchmarks', exist_ok=True)
    
    for k in range(len(files)):
        fig, ax = plt.subplots(figsize=(8.5, 6))

        max_value = max([ys[key][k] for key in ys.keys()])
        
        j  = 0
        for key in ys.keys():
            y = ys[key][k]
            bars = ax.bar([j], [y], width, label=key)
            ax.text(j, y + max_value * 0.02, f'{y:.2f}s', 
                   ha='center', va='bottom', fontsize=10, fontweight='bold')
            j += width

        ax.set_ylim(0, max_value * 1.15)
        
        flows_count = data[k]["data"][0]["flows"]
        
        ax.set_xlabel('Topology '  + files[k])
        ax.set_ylabel('Execution Time (s)')
        ax.set_title(f'Execution Time - {flows_count:,} flows')
        ax.set_xticks([])
        ax.legend()
        ax.grid(True, axis='y', linestyle='--', alpha=0.6)

        plt.tight_layout()
        
        filename = f'benchmarks/benchmark_{files[k]}.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()

def save_test_result(data):
    import json
    with open('results.json', 'w') as f:
        json.dump(data, f)

def read_results():
    import json

    with open('results.json', 'r') as f:
        data = json.load(f)

    return data


def main():
    # data = full_test()
    # save_test_result(data)
    data  = read_results()
    generate_graphs(data)
    return


if __name__ == "__main__":
    main() 