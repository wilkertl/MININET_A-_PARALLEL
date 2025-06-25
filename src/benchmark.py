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
    #print(f"\nA* Router:")
    
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
            #print(f"  Sequential: {len(flows_seq)} flows in {seq_time:.2f}s")
        except Exception as e:
            print(f"  Sequential: ERROR - {e}")
            results['sequential'] = None
            
        return results
        
    except Exception as e:
        print(f"  Initialization ERROR: {e}")
        return {'name': 'A* Router', 'error': str(e)}
    
def benchmark_astar_router_parallel(topo_file) -> dict:
    """Test A* router (both sequential and parallel)"""
    #print(f"\nA* Router:")
    
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
            #print(f"  Parallel: {len(flows_par)} flows in {par_time:.2f}s")
        except Exception as e:
            print(f"  Parallel: ERROR - {e}")
            results['parallel'] = None
            
        return results
        
    except Exception as e:
        print(f"  Initialization ERROR: {e}")
        return {'name': 'A* Router', 'error': str(e)}

def benchmark_dijkstra_router(topo_file) -> dict:
    """Test Dijkstra router (parallel only)"""
    #print(f"\nDijkstra Router:")
    
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
            #print(f"  Parallel: {len(flows)} flows in {par_time:.2f}s")
        except Exception as e:
            print(f"  Parallel: ERROR - {e}")
            results['parallel'] = None
            
        return results
        
    except Exception as e:
        print(f"  Initialization ERROR: {e}")
        return {'name': 'Dijkstra Router', 'error': str(e)}

def benchmark_pycuda_router(topo_file) -> dict:
    """Test PyCUDA router (GPU-accelerated only)"""
    #print(f"\nPyCUDA Router:")
    
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
            #print(f"  GPU-accelerated: {len(flows)} flows in {gpu_time:.2f}s")
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
    i = 0
    for file in files:
        x_num.append(i)
        i+= 1.5

    fig, ax = plt.subplots(figsize=(10, 6))

    j  = 0
    print()
    for key in ys.keys():
        x = [i + (width * j) for i in x_num]
        print(x)
        ax.bar(x, ys[key], width, label=key)
        j += 1

    ax.set_xlabel('Topology')
    ax.set_ylabel('Execution Time (s)')
    ax.set_title('Execution Time')
    ax.set_xticks(x)
    ax.set_xticklabels(files, rotation=45, ha='right')
    ax.legend()
    ax.grid(True, axis='y', linestyle='--', alpha=0.6)

    plt.tight_layout()
    plt.show()


def main():
    generate_graphs( full_test() )
    return
    print("=== Router Performance Benchmark ===")
    
    results = []
    
    # Test A* router (sequential + parallel)
    astar_result = benchmark_astar_router()
    results.append(astar_result)
    
    # Test Dijkstra router (parallel only)
    dijkstra_result = benchmark_dijkstra_router()
    results.append(dijkstra_result)
    
    # Test PyCUDA router (GPU only)
    if PYCUDA_AVAILABLE:
        pycuda_result = benchmark_pycuda_router()
        results.append(pycuda_result)
    else:
        print("\nPyCUDA Router: NOT AVAILABLE (install pycuda)")
    
    # Performance ranking
    print("\n=== Performance Summary ===")
    
    all_times = []
    for result in results:
        if 'error' in result:
            continue
        for mode in ['sequential', 'parallel', 'gpu_accelerated']:
            if result.get(mode):
                mode_display = mode.replace('_', '-')
                all_times.append((f"{result['name']} ({mode_display})", result[mode]['time'], result[mode]['flows']))
    
    if all_times:
        # Sort by time (fastest first)
        all_times.sort(key=lambda x: x[1])
        slowest_time = all_times[-1][1]
        
        print("Ranking (fastest first):")
        for i, (name, time_taken, flow_count) in enumerate(all_times, 1):
            speedup = slowest_time / time_taken
            print(f"{i}. {name}: {time_taken:.2f}s - {flow_count} flows ({speedup:.2f}x speedup)")
    
    # Summary
    print("\n=== Overall Summary ===")
    if all_times:
        fastest = all_times[0]
        print(f"🏆 Fastest: {fastest[0]} - {fastest[1]:.2f}s ({fastest[2]} flows)")
        
        if len(all_times) > 1:
            gpu_results = [x for x in all_times if 'gpu-accelerated' in x[0]]
            cpu_results = [x for x in all_times if 'gpu-accelerated' not in x[0]]
            
            if gpu_results and cpu_results:
                fastest_gpu = gpu_results[0]
                fastest_cpu = min(cpu_results, key=lambda x: x[1])
                
                if fastest_gpu[1] < fastest_cpu[1]:
                    gpu_advantage = fastest_cpu[1] / fastest_gpu[1]
                    print(f"🚀 GPU Advantage: {gpu_advantage:.2f}x faster than best CPU")
                else:
                    cpu_advantage = fastest_gpu[1] / fastest_cpu[1]
                    print(f"🖥️  CPU Advantage: {cpu_advantage:.2f}x faster than GPU")

if __name__ == "__main__":
    main() 