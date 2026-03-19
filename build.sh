#!/bin/bash

# Exit on error
set -e

echo "Removing existing build directories..."
rm -rf dist_package build_temp customer_package

echo "Running customer package build script..."
python3 build_customer_package.py

echo "Creating archive..."
cd customer_package
tar -czf power-monitor-installer.tar.gz power-monitor/
cd ..

echo "Build complete! Archive generated at customer_package/power-monitor-installer.tar.gz"
