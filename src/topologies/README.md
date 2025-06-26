# Topologies

This directory contains network topology files used for routing benchmarks and testing.

## File Format

- **JSON files**: Complete network topology data containing:
  - `distances`: Distance values between directly connected nodes (host↔switch, switch↔switch)
  - `bandwidth`: Link capacity information for each connection
- Only contains distances for nodes that have direct links between them
- The complete network topology can be reconstructed from this connection data

## Usage

These topology files are automatically loaded by the benchmark system to test different routing algorithms across various network sizes and configurations. The routing algorithms use the distance and bandwidth data to calculate optimal paths between all network nodes. 