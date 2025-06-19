#!/bin/bash

# Setup script for Python 3 environment
echo "Setting up Python 3 environment for MININET_A-_PARALLEL..."

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

# Check Python 3 version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Make scripts executable
echo "Making scripts executable..."
chmod +x src/*.py

echo "Setup complete! To activate the environment, run:"
echo "source .venv/bin/activate"
echo ""
echo "To run the Mininet script:"
echo "sudo python3 src/run_tata_mininet.py" 