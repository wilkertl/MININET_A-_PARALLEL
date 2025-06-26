# GPU Configuration Analysis

This directory contains detailed analysis charts for GPU parallelism parameter optimization on CUDA-accelerated routing algorithms.

## Content

- **PNG files**: Performance analysis charts comparing different CUDA configurations
- Each chart analyzes the impact of specific GPU parameters on execution time
- Tests performed on the heaviest network topology (>1M flows)

## Chart Types

### Overall Performance Comparison
- **File**: `overall_performance.png`
- **Description**: Bar chart comparing all tested GPU configurations
- **Shows**: Execution time for each parameter combination
- **Values**: Exact timing displayed above each bar

### Parameter Impact Analysis
- **Block Size Impact** (`block_size_impact.png`): Effect of CUDA block sizes (128, 256, 512, 1024)
- **Batch Size Impact** (`batch_size_impact.png`): Effect of processing batch sizes (500, 1K, 2K, 5K)
- **Grid Multiplier Impact** (`grid_multiplier_impact.png`): Effect of grid size multipliers (1x, 2x, 4x)

## Configuration Parameters

### Block Size
- **Range**: 128 - 1024 threads per block
- **Impact**: Affects GPU occupancy and memory access patterns
- **Optimal**: Varies by GPU architecture

### Batch Size  
- **Range**: 500 - 5000 host pairs per batch
- **Impact**: Determines GPU memory utilization and throughput
- **Optimal**: Larger batches generally improve performance

### Grid Multiplier
- **Range**: 1x - 4x base grid size
- **Impact**: Controls parallel execution units
- **Optimal**: Depends on problem size and GPU capacity

### Path Length
- **Range**: 16 - 128 maximum path nodes
- **Impact**: Affects memory requirements and kernel complexity
- **Optimal**: Should match network topology characteristics

## Generation

Charts are automatically generated when running the GPU configuration benchmark via `python src/benchmark_gpu.py`.