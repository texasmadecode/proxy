# Master Proxy Tests

Automated tests for all 6 proxy modes and endpoints.

## Running Tests Locally

### Quick Test (Bash script)
```bash
./run_tests.sh
```

### Python Unit Tests
```bash
cd tests
python test_master_proxy.py
```

### Manual Testing
```bash
# Start server
python3 master_proxy.py

# In another terminal, test endpoints:
curl http://localhost:5000/
curl -I "http://localhost:5000/video-proxy?url=https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
curl "http://localhost:5000/ultra/?url=https://example.com" | head -50
```

## Test Coverage

### Test Classes

1. **TestHomepage** - Homepage and mode selector
   - Homepage loads (200 OK)
   - All 6 modes listed
   - Stats displayed

2. **TestFlixHQMode** - FlixHQ streaming proxy
   - Endpoint accessible
   - JavaScript interceptor injected
   - Status banner present

3. **TestVideoProxy** - Video streaming
   - Requires url parameter
   - Streams MP4 files
   - CORS headers present
   - Valid video format

4. **TestIframeProxy** - Iframe proxying
   - Requires url parameter
   - Fetches and proxies HTML
   - Interceptor injected
   - CORS headers present

5. **TestUltraMode** - Complete inlining
   - Works with url parameter
   - Shows banner
   - Request blocker injected

6. **TestStealthMode** - JSON disguise
   - Endpoint accessible
   - Stealth script injected

7. **TestUtilityFunctions** - Error handling
   - 404 for invalid paths
   - HEAD request support
   - Large query parameter handling

8. **TestPerformance** - Speed and reliability
   - Homepage loads quickly (<2s)
   - Handles concurrent requests

## GitHub Actions Workflows

### `.github/workflows/test.yml` - Main CI Pipeline

Runs on: Push to main/develop, Pull Requests

Jobs:
- **test** - Run unit tests on Python 3.9, 3.10, 3.11
- **lint** - Code quality checks (flake8, pylint)
- **security** - Security scans (bandit, safety)
- **integration** - Full integration test with running server
- **docker** - Docker build and container test
- **performance** - Response time benchmarks

### `.github/workflows/deploy.yml` - Documentation

Deploys documentation to GitHub Pages on push to main.

## Test Results

Tests validate:
- ✅ All 6 proxy modes accessible
- ✅ Video streaming works (MP4 format)
- ✅ CORS headers present
- ✅ Error handling (400/404/500)
- ✅ Performance (<2s homepage load)
- ✅ Concurrent request handling
- ✅ Python 3.9+ compatibility

## Common Test Failures

### "Server not running"
- Ensure port 5000 is free
- Check if another proxy instance is running
- Increase `SERVER_STARTUP_WAIT` in test config

### "Video proxy timeout"
- Sample video URL may be temporarily unavailable
- Internet connection required for video streaming tests
- Tests will skip if URL unreachable

### "FlixHQ mode failed"
- FlixHQ.to may be down or blocked
- Tests will skip if target site unreachable
- Expected behavior for external dependencies

## Adding New Tests

1. Create test method in appropriate class:
```python
def test_new_feature(self):
    """Test description"""
    resp = requests.get(f"{BASE_URL}/endpoint")
    self.assertEqual(resp.status_code, 200)
```

2. Run tests:
```bash
python test_master_proxy.py
```

3. Test will automatically run in CI on next push

## Continuous Integration

Every commit triggers:
1. Syntax validation
2. Unit tests (all modes)
3. Integration tests (running server)
4. Security scans
5. Code quality checks
6. Docker build test
7. Performance benchmarks

View results: GitHub Actions tab in repository

## Test Dependencies

```
flask>=2.3.0
requests>=2.31.0
flask-sock>=0.7.0
simple-websocket>=1.0.0
pytest>=7.0.0 (optional)
pytest-cov>=4.0.0 (optional)
```

Install: `pip install -r requirements.txt`
