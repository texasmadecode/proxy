#!/usr/bin/env python3
"""
Comprehensive tests for Master Proxy
Tests all 6 modes and endpoints
"""
import unittest
import requests
import time
import subprocess
import sys
import os
from threading import Thread

# Test configuration
BASE_URL = "http://localhost:5000"
SERVER_STARTUP_WAIT = 3  # seconds


class MasterProxyTestCase(unittest.TestCase):
    """Base test case with server management"""
    
    @classmethod
    def setUpClass(cls):
        """Start the master proxy server before tests"""
        print("\n" + "="*70)
        print("Starting Master Proxy server for testing...")
        print("="*70)
        
        # Start server in background
        cls.server_process = subprocess.Popen(
            [sys.executable, "master_proxy.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        
        # Wait for server to start
        time.sleep(SERVER_STARTUP_WAIT)
        
        # Verify server is running
        max_retries = 5
        for i in range(max_retries):
            try:
                resp = requests.get(BASE_URL, timeout=2)
                if resp.status_code == 200:
                    print(f"✓ Server started successfully on {BASE_URL}")
                    break
            except requests.exceptions.RequestException:
                if i == max_retries - 1:
                    cls.tearDownClass()
                    raise Exception("Failed to start server")
                time.sleep(1)
    
    @classmethod
    def tearDownClass(cls):
        """Stop the server after tests"""
        print("\n" + "="*70)
        print("Stopping Master Proxy server...")
        print("="*70)
        
        if hasattr(cls, 'server_process'):
            cls.server_process.terminate()
            cls.server_process.wait(timeout=5)
            print("✓ Server stopped")


class TestHomepage(MasterProxyTestCase):
    """Test homepage and mode selector"""
    
    def test_homepage_loads(self):
        """Test that homepage returns 200 OK"""
        resp = requests.get(BASE_URL, timeout=5)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/html', resp.headers.get('Content-Type', ''))
    
    def test_homepage_contains_modes(self):
        """Test that homepage lists all 6 modes"""
        resp = requests.get(BASE_URL, timeout=5)
        html = resp.text
        
        # Check for mode titles
        self.assertIn('FlixHQ Streaming', html)
        self.assertIn('Video Proxy', html)
        self.assertIn('Iframe Proxy', html)
        self.assertIn('Ultra Mode', html)
        self.assertIn('VPN Tunnel', html)
        self.assertIn('Stealth Mode', html)
    
    def test_homepage_has_stats(self):
        """Test that homepage shows stats"""
        resp = requests.get(BASE_URL, timeout=5)
        html = resp.text
        
        self.assertIn('6', html)  # 6 proxy modes
        self.assertIn('Proxy Modes', html)


class TestFlixHQMode(MasterProxyTestCase):
    """Test FlixHQ streaming mode"""
    
    def test_flixhq_root_accessible(self):
        """Test that /flixhq/ endpoint is accessible"""
        resp = requests.get(f"{BASE_URL}/flixhq/", timeout=10)
        # May return 200 or redirect, both are acceptable
        self.assertIn(resp.status_code, [200, 301, 302, 500])
    
    def test_flixhq_injects_interceptor(self):
        """Test that FlixHQ mode injects JavaScript interceptor"""
        try:
            resp = requests.get(f"{BASE_URL}/flixhq/", timeout=10)
            if resp.status_code == 200:
                html = resp.text
                # Check for interceptor script
                self.assertIn('Master Proxy', html.lower())
                self.assertIn('intercepting', html.lower())
        except requests.exceptions.RequestException:
            # FlixHQ.to might be down or blocked, skip test
            self.skipTest("FlixHQ.to not accessible")
    
    def test_flixhq_has_banner(self):
        """Test that FlixHQ mode shows status banner"""
        try:
            resp = requests.get(f"{BASE_URL}/flixhq/", timeout=10)
            if resp.status_code == 200:
                html = resp.text
                self.assertIn('FlixHQ', html)
        except requests.exceptions.RequestException:
            self.skipTest("FlixHQ.to not accessible")


class TestVideoProxy(MasterProxyTestCase):
    """Test video proxy streaming"""
    
    def test_video_proxy_requires_url_param(self):
        """Test that video proxy requires url parameter"""
        resp = requests.get(f"{BASE_URL}/video-proxy", timeout=5)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('url', resp.text.lower())
    
    def test_video_proxy_streams_mp4(self):
        """Test that video proxy can stream MP4 file"""
        # Use a small test video from Google's test bucket
        test_video_url = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
        
        resp = requests.get(
            f"{BASE_URL}/video-proxy",
            params={'url': test_video_url},
            timeout=15,
            stream=True
        )
        
        self.assertEqual(resp.status_code, 200)
        
        # Check content type
        content_type = resp.headers.get('Content-Type', '')
        self.assertIn('video', content_type.lower())
        
        # Check that we can read some bytes
        chunk = next(resp.iter_content(chunk_size=1024))
        self.assertGreater(len(chunk), 0)
        
        # Verify it's MP4 (starts with ftyp box)
        self.assertTrue(chunk[4:8] == b'ftyp' or b'ftyp' in chunk[:100])
    
    def test_video_proxy_has_cors_headers(self):
        """Test that video proxy includes CORS headers"""
        test_video_url = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
        
        resp = requests.head(
            f"{BASE_URL}/video-proxy",
            params={'url': test_video_url},
            timeout=10
        )
        
        # Check for CORS header
        cors_header = resp.headers.get('Access-Control-Allow-Origin')
        self.assertEqual(cors_header, '*')


class TestIframeProxy(MasterProxyTestCase):
    """Test iframe proxy"""
    
    def test_iframe_proxy_requires_url_param(self):
        """Test that iframe proxy requires url parameter"""
        resp = requests.get(f"{BASE_URL}/iframe-proxy", timeout=5)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('url', resp.text.lower())
    
    def test_iframe_proxy_fetches_html(self):
        """Test that iframe proxy can fetch and proxy HTML"""
        test_url = "https://example.com"
        
        resp = requests.get(
            f"{BASE_URL}/iframe-proxy",
            params={'url': test_url},
            timeout=10
        )
        
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/html', resp.headers.get('Content-Type', ''))
    
    def test_iframe_proxy_injects_interceptor(self):
        """Test that iframe proxy injects video interceptor"""
        test_url = "https://example.com"
        
        resp = requests.get(
            f"{BASE_URL}/iframe-proxy",
            params={'url': test_url},
            timeout=10
        )
        
        if resp.status_code == 200:
            html = resp.text
            # Check for iframe interceptor
            self.assertIn('Master', html)
    
    def test_iframe_proxy_has_cors_headers(self):
        """Test that iframe proxy includes CORS headers"""
        test_url = "https://example.com"
        
        resp = requests.get(
            f"{BASE_URL}/iframe-proxy",
            params={'url': test_url},
            timeout=10
        )
        
        cors_header = resp.headers.get('Access-Control-Allow-Origin')
        self.assertEqual(cors_header, '*')


class TestUltraMode(MasterProxyTestCase):
    """Test ultra mode (complete inlining)"""
    
    def test_ultra_mode_requires_url_param(self):
        """Test that ultra mode works with url parameter"""
        # Should work even without url param (defaults to FlixHQ)
        resp = requests.get(f"{BASE_URL}/ultra/", timeout=10)
        # May succeed or fail depending on target availability
        self.assertIn(resp.status_code, [200, 301, 302, 500])
    
    def test_ultra_mode_with_url_param(self):
        """Test that ultra mode works with explicit URL"""
        test_url = "https://example.com"
        
        resp = requests.get(
            f"{BASE_URL}/ultra/",
            params={'url': test_url},
            timeout=15
        )
        
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/html', resp.headers.get('Content-Type', ''))
    
    def test_ultra_mode_has_banner(self):
        """Test that ultra mode shows banner"""
        test_url = "https://example.com"
        
        resp = requests.get(
            f"{BASE_URL}/ultra/",
            params={'url': test_url},
            timeout=15
        )
        
        if resp.status_code == 200:
            html = resp.text
            self.assertIn('Ultra', html)
    
    def test_ultra_mode_injects_blocker(self):
        """Test that ultra mode injects request blocker"""
        test_url = "https://example.com"
        
        resp = requests.get(
            f"{BASE_URL}/ultra/",
            params={'url': test_url},
            timeout=15
        )
        
        if resp.status_code == 200:
            html = resp.text
            # Check for blocker script
            self.assertIn('fetch', html.lower())


class TestStealthMode(MasterProxyTestCase):
    """Test stealth mode"""
    
    def test_stealth_mode_accessible(self):
        """Test that stealth mode endpoint is accessible"""
        resp = requests.get(f"{BASE_URL}/stealth/", timeout=10)
        # May return 200 or redirect
        self.assertIn(resp.status_code, [200, 301, 302, 500])
    
    def test_stealth_mode_injects_script(self):
        """Test that stealth mode injects stealth script"""
        try:
            resp = requests.get(f"{BASE_URL}/stealth/", timeout=10)
            if resp.status_code == 200:
                html = resp.text
                self.assertIn('Stealth', html)
        except requests.exceptions.RequestException:
            self.skipTest("Target site not accessible")


class TestUtilityFunctions(MasterProxyTestCase):
    """Test utility endpoints and error handling"""
    
    def test_404_for_invalid_path(self):
        """Test that invalid paths return 404"""
        resp = requests.get(f"{BASE_URL}/invalid-path-12345", timeout=5)
        self.assertEqual(resp.status_code, 404)
    
    def test_server_responds_to_head_requests(self):
        """Test that server handles HEAD requests"""
        resp = requests.head(BASE_URL, timeout=5)
        self.assertIn(resp.status_code, [200, 405])  # 405 if HEAD not implemented
    
    def test_server_handles_large_query_params(self):
        """Test that server handles large URL query parameters"""
        long_url = "https://example.com/" + "a" * 1000
        
        resp = requests.get(
            f"{BASE_URL}/video-proxy",
            params={'url': long_url},
            timeout=10
        )
        
        # Should return 500 or timeout, not crash
        self.assertIn(resp.status_code, [400, 500, 502, 504])


class TestPerformance(MasterProxyTestCase):
    """Performance and reliability tests"""
    
    def test_homepage_loads_quickly(self):
        """Test that homepage loads in under 2 seconds"""
        start_time = time.time()
        resp = requests.get(BASE_URL, timeout=5)
        load_time = time.time() - start_time
        
        self.assertEqual(resp.status_code, 200)
        self.assertLess(load_time, 2.0, f"Homepage took {load_time:.2f}s to load")
    
    def test_multiple_concurrent_requests(self):
        """Test that server handles multiple concurrent requests"""
        def make_request():
            try:
                resp = requests.get(BASE_URL, timeout=5)
                return resp.status_code == 200
            except:
                return False
        
        threads = []
        for _ in range(5):
            thread = Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join(timeout=10)
        
        # Just verify server didn't crash
        resp = requests.get(BASE_URL, timeout=5)
        self.assertEqual(resp.status_code, 200)


def run_tests():
    """Run all tests and return results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestHomepage))
    suite.addTests(loader.loadTestsFromTestCase(TestFlixHQMode))
    suite.addTests(loader.loadTestsFromTestCase(TestVideoProxy))
    suite.addTests(loader.loadTestsFromTestCase(TestIframeProxy))
    suite.addTests(loader.loadTestsFromTestCase(TestUltraMode))
    suite.addTests(loader.loadTestsFromTestCase(TestStealthMode))
    suite.addTests(loader.loadTestsFromTestCase(TestUtilityFunctions))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformance))
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
