#!/bin/bash

# Exit on error
set -e

# Get the directory of the script
SCRIPT_DIR=$(dirname "$0")
cd "$SCRIPT_DIR/adbfs"

echo "Creating the application..."
briefcase create

echo "Building the application..."
briefcase build

echo "Packaging the application..."
briefcase package

echo "Build complete. The distributable can be found in the dist directory."
