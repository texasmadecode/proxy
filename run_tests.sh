#!/bin/bash
# Local test runner for Master Proxy
# Run this before committing to verify everything works

set -e

echo "=================================="
echo "Master Proxy - Local Test Runner"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 found${NC}"

# Check if master_proxy.py exists
if [ ! -f "master_proxy.py" ]; then
    echo -e "${RED}✗ master_proxy.py not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ master_proxy.py found${NC}"

# Check Python syntax
echo ""
echo "Checking Python syntax..."
if python3 -m py_compile master_proxy.py; then
    echo -e "${GREEN}✓ Python syntax valid${NC}"
else
    echo -e "${RED}✗ Python syntax errors found${NC}"
    exit 1
fi

# Install dependencies
echo ""
echo "Installing dependencies..."
if pip3 install -q flask requests flask-sock simple-websocket 2>/dev/null; then
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${YELLOW}⚠ Warning: Could not install some dependencies${NC}"
fi

# Run unit tests if available
if [ -f "tests/test_master_proxy.py" ]; then
    echo ""
    echo "Running unit tests..."
    if python3 tests/test_master_proxy.py; then
        echo -e "${GREEN}✓ All tests passed${NC}"
    else
        echo -e "${RED}✗ Some tests failed${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ No tests found in tests/ directory${NC}"
fi

# Quick smoke test
echo ""
echo "Running smoke test..."
python3 master_proxy.py > /tmp/master_proxy_test.log 2>&1 &
PROXY_PID=$!
echo "Started proxy server (PID: $PROXY_PID)"

# Wait for server to start
sleep 3

# Test homepage
if curl -f -s http://localhost:5000/ > /dev/null; then
    echo -e "${GREEN}✓ Homepage accessible${NC}"
else
    echo -e "${RED}✗ Homepage not accessible${NC}"
    kill $PROXY_PID 2>/dev/null || true
    cat /tmp/master_proxy_test.log
    exit 1
fi

# Test video proxy endpoint
if curl -f -s -I "http://localhost:5000/video-proxy?url=https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Video proxy accessible${NC}"
else
    echo -e "${YELLOW}⚠ Video proxy test skipped (may require internet)${NC}"
fi

# Stop server
kill $PROXY_PID 2>/dev/null || true
echo -e "${GREEN}✓ Smoke test passed${NC}"

# Check for common issues
echo ""
echo "Checking for common issues..."

if grep -q "TODO\|FIXME" master_proxy.py; then
    echo -e "${YELLOW}⚠ Found TODO/FIXME comments${NC}"
else
    echo -e "${GREEN}✓ No TODO/FIXME comments${NC}"
fi

if grep -qi "password.*=\|secret.*=\|api.key.*=" master_proxy.py; then
    echo -e "${RED}✗ Possible hardcoded credentials found${NC}"
    exit 1
else
    echo -e "${GREEN}✓ No hardcoded credentials found${NC}"
fi

# Summary
echo ""
echo "=================================="
echo -e "${GREEN}✓ All checks passed!${NC}"
echo "=================================="
echo ""
echo "Ready to commit. Run:"
echo "  git add ."
echo "  git commit -m 'Your message'"
echo "  git push"
echo ""
