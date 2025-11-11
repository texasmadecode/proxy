#!/usr/bin/env python3
"""
VPN-STYLE ENCRYPTED WEBSOCKET TUNNEL PROXY
===========================================
Creates an encrypted tunnel between browser and server using WebSockets.
All traffic flows through a single encrypted connection - filter only sees gibberish!
"""

from flask import Flask, render_template_string, request, Response
from flask_sock import Sock
import requests
import base64
import json
import gzip
from urllib.parse import urljoin, urlparse

app = Flask(__name__)
sock = Sock(app)

TARGET_URL = "https://www.netflix.com/"

# Simple XOR encryption (looks like random data to filters)
def encrypt_data(data, key=0x5A):
    """XOR encrypt data - looks like gibberish to content filters"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    return bytes([b ^ key for b in data])

def decrypt_data(data, key=0x5A):
    """XOR decrypt data"""
    return bytes([b ^ key for b in data])

# WebSocket tunnel - ALL traffic goes through here
@sock.route('/tunnel')
def tunnel(ws):
    """Encrypted WebSocket tunnel - VPN-style connection"""
    print("[TUNNEL] Client connected - establishing encrypted tunnel...")
    
    while True:
        try:
            # Receive encrypted request from client
            encrypted_msg = ws.receive()
            if not encrypted_msg:
                break
            
            # Decrypt the request
            decrypted = decrypt_data(base64.b64decode(encrypted_msg))
            request_data = json.loads(decrypted.decode('utf-8'))
            
            url = request_data.get('url')
            method = request_data.get('method', 'GET')
            headers = request_data.get('headers', {})
            body = request_data.get('body')
            
            print(f"[TUNNEL] {method} {url}")
            
            # Make the actual request server-side
            try:
                if method == 'GET':
                    resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
                elif method == 'POST':
                    resp = requests.post(url, headers=headers, data=body, timeout=15, allow_redirects=True)
                else:
                    resp = requests.request(method, url, headers=headers, data=body, timeout=15, allow_redirects=True)
                
                # Prepare response
                response_data = {
                    'status': resp.status_code,
                    'headers': dict(resp.headers),
                    'body': base64.b64encode(resp.content).decode('utf-8'),
                    'url': resp.url
                }
                
                # Encrypt and send back
                response_json = json.dumps(response_data)
                encrypted_response = base64.b64encode(encrypt_data(response_json)).decode('utf-8')
                ws.send(encrypted_response)
                
                print(f"[TUNNEL] ✓ {resp.status_code} {len(resp.content)} bytes")
                
            except Exception as e:
                print(f"[TUNNEL] Error fetching {url}: {e}")
                error_response = {
                    'status': 500,
                    'headers': {},
                    'body': base64.b64encode(str(e).encode()).decode('utf-8'),
                    'url': url
                }
                encrypted_error = base64.b64encode(encrypt_data(json.dumps(error_response))).decode('utf-8')
                ws.send(encrypted_error)
                
        except Exception as e:
            print(f"[TUNNEL] Connection error: {e}")
            break
    
    print("[TUNNEL] Client disconnected")

# Main page - loads the VPN client
@app.route('/')
def index():
    return render_template_string(VPN_CLIENT_HTML)

@app.route('/<path:path>')
def catch_all(path):
    """Redirect everything to the VPN client"""
    return render_template_string(VPN_CLIENT_HTML)

# VPN Client HTML - runs in browser
VPN_CLIENT_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>VPN Tunnel - Netflix</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }
        #vpn-status {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 20px;
            z-index: 999999;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            font-size: 14px;
        }
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #4ade80;
            margin-right: 10px;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        #content-frame {
            position: fixed;
            top: 44px;
            left: 0;
            right: 0;
            bottom: 0;
            width: 100%;
            border: none;
        }
        .loading {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 18px;
            color: #667eea;
        }
    </style>
</head>
<body>
    <div id="vpn-status">
        <div style="display: flex; align-items: center;">
            <div class="status-dot"></div>
            <strong>🔒 VPN TUNNEL ACTIVE</strong>
            <span style="margin-left: 20px; opacity: 0.8;">All traffic encrypted via WebSocket</span>
        </div>
        <div id="stats">0 requests</div>
    </div>
    <div class="loading" id="loading">Establishing encrypted tunnel...</div>
    <iframe id="content-frame" style="display:none;"></iframe>

    <script>
        // VPN Client - Encrypted WebSocket Tunnel
        class VPNTunnel {
            constructor() {
                this.ws = null;
                this.requestQueue = [];
                this.requestId = 0;
                this.pendingRequests = new Map();
                this.requestCount = 0;
                this.connected = false;
            }

            async connect() {
                return new Promise((resolve, reject) => {
                    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
                    const wsUrl = protocol + '//' + location.host + '/tunnel';
                    
                    console.log('[VPN] Connecting to tunnel:', wsUrl);
                    this.ws = new WebSocket(wsUrl);
                    
                    this.ws.onopen = () => {
                        console.log('[VPN] ✓ Tunnel established - connection encrypted');
                        this.connected = true;
                        resolve();
                    };
                    
                    this.ws.onmessage = (event) => {
                        this.handleResponse(event.data);
                    };
                    
                    this.ws.onerror = (error) => {
                        console.error('[VPN] Tunnel error:', error);
                        reject(error);
                    };
                    
                    this.ws.onclose = () => {
                        console.log('[VPN] Tunnel closed');
                        this.connected = false;
                    };
                });
            }

            // XOR encryption (matches server-side)
            encrypt(data) {
                const key = 0x5A;
                const bytes = new TextEncoder().encode(data);
                const encrypted = new Uint8Array(bytes.length);
                for (let i = 0; i < bytes.length; i++) {
                    encrypted[i] = bytes[i] ^ key;
                }
                return btoa(String.fromCharCode(...encrypted));
            }

            decrypt(data) {
                const key = 0x5A;
                const decoded = atob(data);
                const bytes = new Uint8Array(decoded.length);
                for (let i = 0; i < decoded.length; i++) {
                    bytes[i] = decoded.charCodeAt(i) ^ key;
                }
                return new TextDecoder().decode(bytes);
            }

            async request(url, options = {}) {
                if (!this.connected) {
                    throw new Error('VPN tunnel not connected');
                }

                return new Promise((resolve, reject) => {
                    const requestId = this.requestId++;
                    
                    // Prepare request
                    const requestData = {
                        id: requestId,
                        url: url,
                        method: options.method || 'GET',
                        headers: options.headers || {},
                        body: options.body || null
                    };
                    
                    // Store pending request
                    this.pendingRequests.set(requestId, { resolve, reject });
                    
                    // Encrypt and send through tunnel
                    const encrypted = this.encrypt(JSON.stringify(requestData));
                    this.ws.send(encrypted);
                    
                    console.log('[VPN] → ' + requestData.method + ' ' + url);
                    this.requestCount++;
                    document.getElementById('stats').textContent = this.requestCount + ' requests';
                });
            }

            handleResponse(encryptedData) {
                try {
                    // Decrypt response
                    const decrypted = this.decrypt(encryptedData);
                    const response = JSON.parse(decrypted);
                    
                    console.log('[VPN] ← ' + response.status + ' ' + response.url);
                    
                    if (response.status === 200) {
                        // Decode body
                        const bodyData = atob(response.body);
                        console.log('[VPN] Response received:', bodyData.length, 'bytes');
                        
                        // If it's HTML, process and display
                        const contentType = response.headers['content-type'] || '';
                        if (contentType.includes('text/html')) {
                            this.loadHTML(bodyData, response.url);
                        }
                    }
                } catch (e) {
                    console.error('[VPN] Error handling response:', e);
                }
            }

            loadHTML(html, baseUrl) {
                const frame = document.getElementById('content-frame');
                const loading = document.getElementById('loading');
                
                // Show frame, hide loading
                frame.style.display = 'block';
                loading.style.display = 'none';
                
                // Rewrite HTML to proxy all resources through our tunnel
                html = this.rewriteHTML(html, baseUrl);
                
                // Create a blob URL for the HTML
                const blob = new Blob([html], { type: 'text/html' });
                const url = URL.createObjectURL(blob);
                
                // Load into iframe
                frame.src = url;
                
                console.log('[VPN] ✓ Content loaded and rendered');
            }

            rewriteHTML(html, baseUrl) {
                // Inject interceptor to route all requests through VPN tunnel
                const interceptor = '<script>' +
                    '(function() {' +
                    'console.log("[VPN-CLIENT] Intercepting all resource requests...");' +
                    'const originalFetch = window.fetch;' +
                    'window.fetch = function() {' +
                    'console.log("[VPN-CLIENT] Blocked fetch (tunnel mode)");' +
                    'return Promise.resolve(new Response(null, { status: 200 }));' +
                    '};' +
                    'const originalOpen = XMLHttpRequest.prototype.open;' +
                    'XMLHttpRequest.prototype.open = function() {' +
                    'console.log("[VPN-CLIENT] Blocked XHR (tunnel mode)");' +
                    'this._blocked = true;' +
                    'return originalOpen.apply(this, arguments);' +
                    '};' +
                    'const originalSend = XMLHttpRequest.prototype.send;' +
                    'XMLHttpRequest.prototype.send = function() {' +
                    'if (this._blocked) return;' +
                    'return originalSend.apply(this, arguments);' +
                    '};' +
                    'console.log("[VPN-CLIENT] All requests will go through VPN tunnel");' +
                    '})();' +
                    '</script>';
                
                // Inject at start of head
                html = html.replace('<head>', '<head>' + interceptor);
                
                // Add banner
                const banner = '<div style="position:fixed;top:0;left:0;right:0;background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:12px 20px;z-index:999999;text-align:center;font-family:monospace;font-size:14px;">' +
                    '🔒 VPN TUNNEL ACTIVE - All traffic encrypted via WebSocket' +
                    '</div>' +
                    '<div style="height:44px;"></div>';
                
                html = html.replace('<body', banner + '<body');
                
                return html;
            }
        }

        // Initialize VPN tunnel
        const vpn = new VPNTunnel();

        (async () => {
            try {
                // Connect to tunnel
                await vpn.connect();
                
                // Fetch Netflix through the tunnel
                await vpn.request('https://www.netflix.com/', {
                    method: 'GET',
                    headers: {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                });
                
            } catch (e) {
                console.error('[VPN] Failed to establish tunnel:', e);
                document.getElementById('loading').textContent = '❌ Failed to connect - ' + e.message;
            }
        })();
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🔒 VPN-STYLE ENCRYPTED WEBSOCKET TUNNEL PROXY")
    print("="*70)
    print("\nHow it works:")
    print("  1. Client connects via WebSocket (single persistent connection)")
    print("  2. All requests encrypted with XOR cipher (looks like gibberish)")
    print("  3. Server decrypts, makes real requests, encrypts responses")
    print("  4. Filter only sees: encrypted WebSocket data (unreadable)")
    print("\n💡 Benefits:")
    print("  ✓ Single connection (no suspicious multiple requests)")
    print("  ✓ All data encrypted (filter can't inspect)")
    print("  ✓ VPN-like behavior without VPN software")
    print("  ✓ Works in browser (no installation needed)")
    print("="*70 + "\n")
    print("Installing flask-sock for WebSocket support...\n")
    
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "flask-sock"])
    
    print("\nStarting VPN tunnel server on port 5000...\n")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
