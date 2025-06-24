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





# Advanced CUDA kernel for batch path reconstruction (GPU-optimized)
cuda_batch_paths_kernel = """
#define INFNTY 1e9f
#define MAX_PATH_LENGTH 64

__global__ void reconstruct_paths_batch(
    int num_pairs,
    int V,
    int* host_pairs,           // [num_pairs, 2] - source and target indices
    float* distance_matrix,    // [V, V] - precomputed distances  
    float* adjacency_matrix,   // [V, V] - adjacency weights
    int* paths_output,         // [num_pairs, MAX_PATH_LENGTH] - reconstructed paths
    int* path_lengths          // [num_pairs] - actual path lengths
)
{
    int pair_idx = blockIdx.x * blockDim.x + threadIdx.x;
    
    if (pair_idx >= num_pairs) return;
    
    int source = host_pairs[pair_idx * 2];
    int target = host_pairs[pair_idx * 2 + 1];
    
    // Initialize path length
    path_lengths[pair_idx] = 0;
    
    if (source < 0 || source >= V || target < 0 || target >= V) return;
    if (distance_matrix[source * V + target] >= INFNTY) return;
    
    // Same source and target
    if (source == target) {
        paths_output[pair_idx * MAX_PATH_LENGTH] = source;
        path_lengths[pair_idx] = 1;
        return;
    }
    
    // Reconstruct path using backtracking
    int path[MAX_PATH_LENGTH];
    int path_len = 0;
    
    path[path_len++] = target;
    int current = target;
    
    while (current != source && path_len < MAX_PATH_LENGTH - 1) {
        int best_predecessor = -1;
        float min_dist = INFNTY;
        
        // Find predecessor with minimum distance + edge weight = current distance
        for (int predecessor = 0; predecessor < V; predecessor++) {
            if (adjacency_matrix[predecessor * V + current] > 0.0f) {
                float pred_dist = distance_matrix[source * V + predecessor];
                float edge_weight = adjacency_matrix[predecessor * V + current];
                float total_dist = distance_matrix[source * V + current];
                
                if (fabsf(pred_dist + edge_weight - total_dist) < 1e-6f) {
                    if (pred_dist < min_dist) {
                        min_dist = pred_dist;
                        best_predecessor = predecessor;
                    }
                }
            }
        }
        
        if (best_predecessor == -1) break;
        
        path[path_len++] = best_predecessor;
        current = best_predecessor;
    }
    
    // Reverse path and copy to output
    if (current == source && path_len >= 2) {
        for (int i = 0; i < path_len; i++) {
            paths_output[pair_idx * MAX_PATH_LENGTH + i] = path[path_len - 1 - i];
        }
        path_lengths[pair_idx] = path_len;
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

def reconstruct_paths_batch_gpu(host_pairs, distance_matrix, adjacency_matrix, node_to_index, index_to_node):
    """
    GPU-accelerated batch path reconstruction
    Processes multiple host pairs simultaneously on GPU
    """
    if not PYCUDA_AVAILABLE:
        return []
    
    try:
        import pycuda.gpuarray as gpuarray
        from pycuda.compiler import SourceModule
        import pycuda.driver as cuda
        
        V = distance_matrix.shape[0]
        num_pairs = len(host_pairs)
        MAX_PATH_LENGTH = 64
        
        if num_pairs == 0:
            return []
        
        # Prepare host pairs array (convert MAC addresses to indices)
        host_pairs_indices = []
        valid_mac_pairs = []
        
        for source_mac, target_mac in host_pairs:
            if source_mac in node_to_index and target_mac in node_to_index:
                source_idx = node_to_index[source_mac]
                target_idx = node_to_index[target_mac]
                host_pairs_indices.extend([source_idx, target_idx])
                valid_mac_pairs.append((source_mac, target_mac))
        
        if len(host_pairs_indices) == 0:
            return []
        
        num_valid_pairs = len(host_pairs_indices) // 2
        
        # Compile advanced kernel
        mod = SourceModule(cuda_batch_paths_kernel)
        kernel = mod.get_function("reconstruct_paths_batch")
        
        # Prepare GPU arrays
        d_host_pairs = gpuarray.to_gpu(np.array(host_pairs_indices, dtype=np.int32))
        d_distance_matrix = gpuarray.to_gpu(distance_matrix.flatten().astype(np.float32))
        d_adjacency_matrix = gpuarray.to_gpu(adjacency_matrix.flatten().astype(np.float32))
        d_paths_output = gpuarray.zeros((num_valid_pairs, MAX_PATH_LENGTH), dtype=np.int32)
        d_path_lengths = gpuarray.zeros(num_valid_pairs, dtype=np.int32)
        
        # Configure kernel launch
        block_size = 256
        grid_size = (num_valid_pairs + block_size - 1) // block_size
        
        # Launch batch path reconstruction kernel
        kernel(
            np.int32(num_valid_pairs),
            np.int32(V),
            d_host_pairs,
            d_distance_matrix,
            d_adjacency_matrix,
            d_paths_output,
            d_path_lengths,
            block=(block_size, 1, 1),
            grid=(grid_size, 1)
        )
        
        # Synchronize and get results
        cuda.Context.synchronize()
        paths_output = d_paths_output.get()
        path_lengths = d_path_lengths.get()
        
        # Convert results to path lists
        valid_paths = []
        for i in range(num_valid_pairs):
            path_len = path_lengths[i]
            if path_len >= 2:  # Valid path
                path_indices = paths_output[i, :path_len]
                path_nodes = [index_to_node[idx] for idx in path_indices]
                valid_paths.append(path_nodes)
        
        return valid_paths
        
    except Exception as e:
        print(f"GPU batch path reconstruction failed: {e}")
        return []