#!/usr/bin/env python3
"""
Benchmark comparing router implementations
"""

import sys
import os
import time
from typing import Dict, List

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

def benchmark_router(router_class, name: str) -> Dict:
    """Test a router and return timing results"""
    print(f"\n{name}:")
    
    try:
        router = router_class()
        router.update()
        
        results = {'name': name}
        
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
        return {'name': name, 'error': str(e)}

def main():
    print("=== Router Benchmark ===")
    
    results = []
    
    # Test each router
    #results.append(benchmark_router(Router, "A* Router"))
    #results.append(benchmark_router(RouterDijkstra, "Dijkstra Router"))
    
    if PYCUDA_AVAILABLE:
        results.append(benchmark_router(RouterPyCUDA, "PyCUDA Router"))
    else:
        print("\nPyCUDA Router: NOT AVAILABLE")
    
    # Calculate speedups
    print("\n=== Summary ===")
    
    all_times = []
    for result in results:
        if 'error' in result:
            continue
        for mode in ['sequential', 'parallel']:
            if result.get(mode):
                all_times.append((f"{result['name']} ({mode})", result[mode]['time']))
    
    if all_times:
        # Sort by time (fastest first)
        all_times.sort(key=lambda x: x[1])
        slowest_time = all_times[-1][1]
        
        print("Ranking (fastest first):")
        for i, (name, time_taken) in enumerate(all_times, 1):
            speedup = slowest_time / time_taken
            print(f"{i}. {name}: {time_taken:.2f}s ({speedup:.2f}x)")

if __name__ == "__main__":
    main() 