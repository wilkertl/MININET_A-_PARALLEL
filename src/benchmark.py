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

def benchmark_astar_router() -> dict:
    """Test A* router (both sequential and parallel)"""
    print(f"\nA* Router:")
    
    try:
        router = Router()
        router.update()
        
        results = {'name': 'A* Router'}
        
        # Sequential test
        try:
            start = time.time()
            flows_seq = router.install_all_routes(parallel=False)
            seq_time = time.time() - start
            results['sequential'] = {'time': seq_time, 'flows': len(flows_seq)}
            print(f"  Sequential: {len(flows_seq)} flows in {seq_time:.2f}s")
        except Exception as e:
            print(f"  Sequential: ERROR - {e}")
            results['sequential'] = None
        
        # Parallel test
        try:
            start = time.time()
            flows_par = router.install_all_routes(parallel=True)
            par_time = time.time() - start
            results['parallel'] = {'time': par_time, 'flows': len(flows_par)}
            print(f"  Parallel: {len(flows_par)} flows in {par_time:.2f}s")
        except Exception as e:
            print(f"  Parallel: ERROR - {e}")
            results['parallel'] = None
            
        return results
        
    except Exception as e:
        print(f"  Initialization ERROR: {e}")
        return {'name': 'A* Router', 'error': str(e)}

def benchmark_dijkstra_router() -> dict:
    """Test Dijkstra router (parallel only)"""
    print(f"\nDijkstra Router:")
    
    try:
        router = RouterDijkstra()
        router.update()
        
        results = {'name': 'Dijkstra Router'}
        
        # Parallel test only
        try:
            start = time.time()
            flows = router.install_all_routes(parallel=True)
            par_time = time.time() - start
            results['parallel'] = {'time': par_time, 'flows': len(flows)}
            print(f"  Parallel: {len(flows)} flows in {par_time:.2f}s")
        except Exception as e:
            print(f"  Parallel: ERROR - {e}")
            results['parallel'] = None
            
        return results
        
    except Exception as e:
        print(f"  Initialization ERROR: {e}")
        return {'name': 'Dijkstra Router', 'error': str(e)}

def benchmark_pycuda_router() -> dict:
    """Test PyCUDA router (GPU-accelerated only)"""
    print(f"\nPyCUDA Router:")
    
    try:
        router = RouterPyCUDA()
        router.update()
        
        results = {'name': 'PyCUDA Router'}
        
        # GPU-accelerated test only
        try:
            start = time.time()
            flows = router.install_all_routes()  # Always GPU-optimized
            gpu_time = time.time() - start
            results['gpu_accelerated'] = {'time': gpu_time, 'flows': len(flows)}
            print(f"  GPU-accelerated: {len(flows)} flows in {gpu_time:.2f}s")
        except Exception as e:
            print(f"  GPU-accelerated: ERROR - {e}")
            results['gpu_accelerated'] = None
            
        return results
        
    except Exception as e:
        print(f"  Initialization ERROR: {e}")
        return {'name': 'PyCUDA Router', 'error': str(e)}

def main():
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