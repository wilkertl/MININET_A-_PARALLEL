"""
PyCUDA parallel Dijkstra algorithm implementation
GPU-accelerated all-pairs shortest path computation
"""
import numpy as np
import sys
import concurrent.futures
import math

try:
    import pycuda.autoinit
    import pycuda.driver as cuda
    from pycuda.compiler import SourceModule
    import pycuda.gpuarray as gpuarray
    PYCUDA_AVAILABLE = True
except ImportError:
    PYCUDA_AVAILABLE = False
    print("PyCUDA not available - install with: pip install pycuda")

# CUDA kernel with float32 to avoid overflow
cuda_kernel_code = """
#define TRUE 1
#define FALSE 0
#define INFNTY 1e9f

typedef int boolean;

__global__ void dijkstra_kernel(int V, float *graph, float *len, float *temp_distance, boolean *visited)
{
    int source = blockIdx.x * blockDim.x + threadIdx.x;

    if (source < V)
    {
        // Each thread has its own offset in shared arrays
        int visited_offset = source * V;
        int temp_distance_offset = source * V;
        
        // Initialize arrays for this specific thread
        for (int i = 0; i < V; ++i)
        {
            visited[visited_offset + i] = FALSE;
            temp_distance[temp_distance_offset + i] = INFNTY;
            len[source * V + i] = INFNTY;
        }

        len[source * V + source] = 0.0f;

        for (int count = 0; count < V - 1; ++count)
        {
            int current_vertex = -1;
            float min_distance = INFNTY;

            // Find vertex with minimum distance
            for (int v = 0; v < V; ++v)
            {
                if (!visited[visited_offset + v] && len[source * V + v] <= min_distance)
                {
                    min_distance = len[source * V + v];
                    current_vertex = v;
                }
            }

            if (current_vertex == -1) break;
            visited[visited_offset + current_vertex] = TRUE;

            // Update neighbor distances
            for (int v = 0; v < V; ++v)
            {
                float weight = graph[current_vertex * V + v];
                if (!visited[visited_offset + v] && weight > 0.0f && len[source * V + current_vertex] < INFNTY &&
                    len[source * V + current_vertex] + weight < len[source * V + v])
                {
                    len[source * V + v] = len[source * V + current_vertex] + weight;
                    temp_distance[temp_distance_offset + v] = len[source * V + v];
                }
            }
        }
    }
}
"""

def dijkstra_parallel_pycuda(V, adjacency_matrix):
    """
    PyCUDA parallel Dijkstra implementation with float32
    Computes all-pairs shortest paths using GPU acceleration
    """
    if not PYCUDA_AVAILABLE:
        print("PyCUDA not available!")
        return None, None

    # Compile CUDA kernel
    mod = SourceModule(cuda_kernel_code)
    dijkstra_kernel = mod.get_function("dijkstra_kernel")
    
    # Prepare data with float32
    INFNTY = 1e9
    
    # Convert adjacency matrix to float32
    adjacency_matrix_float = adjacency_matrix.astype(np.float32)
    
    # Output arrays - each thread needs its own space
    len_array = np.full((V, V), INFNTY, dtype=np.float32)
    temp_distance = np.full((V, V), INFNTY, dtype=np.float32)
    visited = np.zeros((V, V), dtype=np.int32)
    
    # Allocate GPU memory
    d_graph = gpuarray.to_gpu(adjacency_matrix_float.flatten())
    d_len = gpuarray.to_gpu(len_array.flatten())
    d_temp_distance = gpuarray.to_gpu(temp_distance.flatten())
    d_visited = gpuarray.to_gpu(visited.flatten())
    
    # Configure grid and block
    block_size = 256
    grid_size = (V + block_size - 1) // block_size
    
    # Execute kernel
    dijkstra_kernel(
        np.int32(V),
        d_graph,
        d_len,
        d_temp_distance,
        d_visited,
        block=(block_size, 1, 1),
        grid=(grid_size, 1)
    )
    
    # Synchronize GPU
    cuda.Context.synchronize()
    
    # Copy results back
    result_len = d_len.get().reshape((V, V))
    result_temp = d_temp_distance.get().reshape((V, V))
    
    return result_len, result_temp

def dijkstra_cpu_worker(source_batch, V, adjacency_matrix):
    """Worker function for parallel Dijkstra computation"""
    INFNTY = 1e9
    batch_results = {}
    
    for source in source_batch:
        distances = np.full(V, INFNTY, dtype=np.float32)
        visited = np.zeros(V, dtype=bool)
        distances[source] = 0.0
        
        for _ in range(V - 1):
            # Find unvisited vertex with minimum distance
            min_dist = INFNTY
            current_vertex = -1
            
            for v in range(V):
                if not visited[v] and distances[v] <= min_dist:
                    min_dist = distances[v]
                    current_vertex = v
            
            if current_vertex == -1:
                break
                
            visited[current_vertex] = True
            
            # Update distances of neighbors
            for v in range(V):
                weight = adjacency_matrix[current_vertex, v]
                if (not visited[v] and weight > 0 and 
                    distances[current_vertex] < INFNTY and
                    distances[current_vertex] + weight < distances[v]):
                    distances[v] = distances[current_vertex] + weight
        
        batch_results[source] = distances
    
    return batch_results

def dijkstra_cpu_parallel(V, adjacency_matrix, max_workers=None):
    """Parallel CPU all-pairs Dijkstra using ProcessPoolExecutor"""
    
    INFNTY = 1e9
    adjacency_matrix = adjacency_matrix.astype(np.float32)
    len_array = np.full((V, V), INFNTY, dtype=np.float32)
    
    # Determine number of workers
    if max_workers is None:
        max_workers = min(16, max(1, V // 4))  # Adaptive worker count
    
    # Create source batches
    sources = list(range(V))
    batch_size = max(1, math.ceil(V / max_workers))
    source_batches = [sources[i:i + batch_size] for i in range(0, V, batch_size)]
    
    # Execute parallel computation
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all batches
        futures = [
            executor.submit(dijkstra_cpu_worker, batch, V, adjacency_matrix)
            for batch in source_batches
        ]
        
        # Collect results
        for future in concurrent.futures.as_completed(futures):
            try:
                batch_results = future.result()
                for source, distances in batch_results.items():
                    len_array[source] = distances
            except Exception as e:
                pass
    
    return len_array

def dijkstra_cpu(V, adjacency_matrix):
    """Sequential CPU all-pairs Dijkstra for comparison"""
    
    INFNTY = 1e9
    adjacency_matrix = adjacency_matrix.astype(np.float32)
    len_array = np.full((V, V), INFNTY, dtype=np.float32)
    
    for source in range(V):
        distances = np.full(V, INFNTY, dtype=np.float32)
        visited = np.zeros(V, dtype=bool)
        distances[source] = 0.0
        
        for _ in range(V - 1):
            # Find unvisited vertex with minimum distance
            min_dist = INFNTY
            current_vertex = -1
            
            for v in range(V):
                if not visited[v] and distances[v] <= min_dist:
                    min_dist = distances[v]
                    current_vertex = v
            
            if current_vertex == -1:
                break
                
            visited[current_vertex] = True
            
            # Update distances of neighbors
            for v in range(V):
                weight = adjacency_matrix[current_vertex, v]
                if (not visited[v] and weight > 0 and 
                    distances[current_vertex] < INFNTY and
                    distances[current_vertex] + weight < distances[v]):
                    distances[v] = distances[current_vertex] + weight
        
        len_array[source] = distances
    
    return len_array