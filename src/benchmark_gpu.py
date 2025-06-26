#!/usr/bin/env python3
"""
GPU Parallelism Configuration Benchmark
Specialized benchmark for testing different GPU configurations on heavy topologies
"""

import sys
import os
import time
import json
import matplotlib.pyplot as plt
import numpy as np

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from router_pycuda import RouterPyCUDA
from dijkstra import dijkstra_parallel_pycuda
import pycuda.driver as cuda
import pycuda.gpuarray as gpuarray
from pycuda.compiler import SourceModule

def find_heaviest_topology():
    """Find the topology with the most flows (>1M)"""
    results_file = 'results.json'
    if not os.path.exists(results_file):
        print("No results.json found. Run main benchmark first.")
        return None
    
    with open(results_file, 'r') as f:
        data = json.load(f)
    
    # Find topology with most flows
    heaviest = None
    max_flows = 0
    
    for topo in data:
        flows = topo["data"][0]["flows"]
        if flows > max_flows:
            max_flows = flows
            heaviest = topo
    
    if max_flows > 1000000:  # More than 1M flows
        print(f"Using heaviest topology: {heaviest['file']} with {max_flows:,} flows")
        return f"topologies/{heaviest['file']}.json"
    else:
        print(f"Heaviest topology has only {max_flows:,} flows. Using it anyway.")
        return f"topologies/{heaviest['file']}.json"

def run_gpu_configuration_benchmark():
    """Run comprehensive GPU configuration benchmark"""
    
    # Find heaviest topology
    topo_file = find_heaviest_topology()
    if not topo_file:
        return
    
    print("=== GPU Configuration Benchmark ===")
    print(f"Testing on: {topo_file}")
    
    # Configuration space to test
    configurations = [
        # (block_size, grid_multiplier, batch_size, max_path_length)
        (128, 1, 1000, 32),   # Small blocks, small batches
        (256, 1, 1000, 32),   # Medium blocks
        (512, 1, 1000, 32),   # Large blocks
        (1024, 1, 1000, 32),  # Very large blocks
        
        (256, 1, 1000, 32),   # Baseline
        (256, 2, 1000, 32),   # Double grid size
        (256, 4, 1000, 32),   # Quad grid size
        
        (256, 1, 500, 32),    # Smaller batches
        (256, 1, 2000, 32),   # Larger batches
        (256, 1, 5000, 32),   # Very large batches
        
        (256, 1, 1000, 16),   # Shorter paths
        (256, 1, 1000, 64),   # Longer paths
        (256, 1, 1000, 128),  # Very long paths
        
        # Optimal combinations
        (512, 2, 2000, 64),   # High performance config
        (256, 4, 5000, 32),   # High throughput config
        (1024, 1, 1000, 128), # High capacity config
    ]
    
    results = []
    
    for i, (block_size, grid_mult, batch_size, max_path) in enumerate(configurations):
        print(f"\nTesting config {i+1}/{len(configurations)}: "
              f"Block={block_size}, Grid×{grid_mult}, Batch={batch_size}, Path={max_path}")
        
        result = benchmark_gpu_config(topo_file, block_size, grid_mult, batch_size, max_path)
        if result:
            results.append(result)
            print(f"  Time: {result['time']:.2f}s, Flows: {result['flows']:,}")
        else:
            print("  FAILED")
    
    # Save results
    with open('gpu_config_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Generate analysis
    generate_gpu_analysis(results)
    
    return results

def benchmark_gpu_config(topo_file, block_size, grid_multiplier, batch_size, max_path_length):
    """Benchmark specific GPU configuration"""
    
    try:
        # Create router with custom GPU configuration
        router = RouterPyCUDA(
            topo_file=topo_file,
            block_size=block_size,
            grid_multiplier=grid_multiplier,
            batch_size=batch_size,
            max_path_length=max_path_length
        )
        router.update()
        
        # Run benchmark with timing
        start_time = time.time()
        flows = router.install_all_routes()
        total_time = time.time() - start_time
        
        return {
            'block_size': block_size,
            'grid_multiplier': grid_multiplier,
            'batch_size': batch_size,
            'max_path_length': max_path_length,
            'time': total_time,
            'flows': len(flows),
            'config_name': f"B{block_size}_G{grid_multiplier}_Batch{batch_size}_Path{max_path_length}"
        }
        
    except Exception as e:
        print(f"GPU config benchmark failed: {e}")
        return None

def generate_gpu_analysis(results):
    """Generate analysis charts for GPU configurations"""
    if not results:
        return
    
    os.makedirs('gpu_analysis', exist_ok=True)
    
    # Extract data
    configs = [r['config_name'] for r in results]
    times = [r['time'] for r in results]
    
    # 1. Overall performance comparison
    plt.figure(figsize=(15, 8))
    bars = plt.bar(range(len(configs)), times, color='skyblue', edgecolor='navy', alpha=0.7)
    plt.xlabel('Configuration')
    plt.ylabel('Execution Time (s)')
    plt.title('GPU Configuration Performance Comparison')
    plt.xticks(range(len(configs)), configs, rotation=45, ha='right')
    
    # Add value labels on bars
    for bar, time_val in zip(bars, times):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f'{time_val:.2f}s', ha='center', va='bottom', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('gpu_analysis/overall_performance.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 2. Block size impact
    block_data = {}
    for r in results:
        bs = r['block_size']
        if bs not in block_data:
            block_data[bs] = []
        block_data[bs].append(r['time'])
    
    plt.figure(figsize=(10, 6))
    block_sizes_unique = sorted(block_data.keys())
    avg_times = [np.mean(block_data[bs]) for bs in block_sizes_unique]
    plt.plot(block_sizes_unique, avg_times, 'o-', linewidth=2, markersize=8)
    plt.xlabel('Block Size')
    plt.ylabel('Average Execution Time (s)')
    plt.title('Impact of Block Size on Performance')
    plt.grid(True, alpha=0.3)
    plt.savefig('gpu_analysis/block_size_impact.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 3. Batch size impact
    batch_data = {}
    for r in results:
        bs = r['batch_size']
        if bs not in batch_data:
            batch_data[bs] = []
        batch_data[bs].append(r['time'])
    
    plt.figure(figsize=(10, 6))
    batch_sizes_unique = sorted(batch_data.keys())
    avg_times = [np.mean(batch_data[bs]) for bs in batch_sizes_unique]
    plt.plot(batch_sizes_unique, avg_times, 's-', linewidth=2, markersize=8, color='orange')
    plt.xlabel('Batch Size')
    plt.ylabel('Average Execution Time (s)')
    plt.title('Impact of Batch Size on Performance')
    plt.grid(True, alpha=0.3)
    plt.savefig('gpu_analysis/batch_size_impact.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 4. Grid multiplier impact
    grid_data = {}
    for r in results:
        gm = r['grid_multiplier']
        if gm not in grid_data:
            grid_data[gm] = []
        grid_data[gm].append(r['time'])
    
    plt.figure(figsize=(10, 6))
    grid_mults_unique = sorted(grid_data.keys())
    avg_times = [np.mean(grid_data[gm]) for gm in grid_mults_unique]
    plt.plot(grid_mults_unique, avg_times, '^-', linewidth=2, markersize=8, color='red')
    plt.xlabel('Grid Multiplier')
    plt.ylabel('Average Execution Time (s)')
    plt.title('Impact of Grid Multiplier on Performance')
    plt.grid(True, alpha=0.3)
    plt.savefig('gpu_analysis/grid_multiplier_impact.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Generated {len(results)} GPU configuration analysis charts in gpu_analysis/")

def main():
    run_gpu_configuration_benchmark()

if __name__ == "__main__":
    main() 