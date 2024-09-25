#!/bin/bash

# Set variables
VERSION="4.23.9.0"
URL="https://github.com/inotify-tools/inotify-tools/archive/refs/tags/$VERSION.tar.gz"
TAR_FILE="inotify-tools-$VERSION.tar.gz"
SRC_DIR="inotify-tools-$VERSION"
LIB_DIR="/usr/local/lib"
CONF_FILE="/etc/ld.so.conf.d/local-lib.conf"

# Download the source code
echo "Downloading inotify-tools $VERSION..."
wget $URL -O $TAR_FILE

# Extract the tarball
echo "Extracting $TAR_FILE..."
tar -xzf $TAR_FILE

# Change to the source directory
cd $SRC_DIR

# Install dependencies
echo "Installing build dependencies..."
apt-get update
apt-get install -y build-essential autoconf automake libtool pkg-config

# Compile and install inotify-tools
echo "Compiling and installing inotify-tools..."
./autogen.sh
./configure
make
make install

# Update the library path
echo "Updating the library path..."
if [ ! -f $CONF_FILE ]; then
    echo $LIB_DIR | sudo tee $CONF_FILE
fi
ldconfig

# Clean up
cd ..
rm -rf $SRC_DIR $TAR_FILE

# Verify the installation
echo "Verifying the installation..."
if command -v inotifywait &> /dev/null; then
    echo "inotifywait installed successfully!"
else
    echo "inotifywait installation failed."
    exit 1
fi
