import requests
import json
import base64
from flask import Flask, render_template_string
from flask_sock import Sock

app = Flask(__name__)
sock = Sock(app)

TARGET_URL = "https://www.netflix.com/"

# HTML page with WebSocket client
HTML_TEMPLATE = '''<!DOCTYPE html>
<html>
<head>
    <title>WebSocket Proxy</title>
    <style>
        body { margin: 0; padding: 0; overflow: hidden; }
        #frame { width: 100vw; height: 100vh; border: none; }
        #status { position: fixed; top: 10px; right: 10px; background: #333; color: #0f0; padding: 10px; border-radius: 5px; font-family: monospace; z-index: 9999; }
    </style>
</head>
<body>
    <div id="status">Connecting...</div>
    <iframe id="frame" sandbox="allow-same-origin allow-scripts allow-forms allow-popups"></iframe>
    
    <script>
        const status = document.getElementById('status');
        const frame = document.getElementById('frame');
        let ws;
        let requestId = 0;
        let pendingRequests = new Map();
        
        function connect() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = protocol + '//' + window.location.host + '/ws';
            console.log('[WS Proxy] Connecting to:', wsUrl);
            ws = new WebSocket(wsUrl);
            
            ws.onopen = () => {
                console.log('[WS Proxy] Connected!');
                status.textContent = 'Connected ✓';
                status.style.background = '#060';
                loadPage('/');
            };
            
            ws.onclose = (event) => {
                console.log('[WS Proxy] Disconnected:', event.code, event.reason);
                status.textContent = 'Disconnected ✗ (code: ' + event.code + ')';
                status.style.background = '#600';
                setTimeout(connect, 2000);
            };
            
            ws.onerror = (err) => {
                console.error('[WS Proxy] WebSocket error:', err);
                status.textContent = 'Error ✗';
                status.style.background = '#600';
            };
            
            ws.onmessage = (event) => {
                try {
                    const response = JSON.parse(event.data);
                    const callback = pendingRequests.get(response.id);
                    if (callback) {
                        callback(response);
                        pendingRequests.delete(response.id);
                    }
                } catch (e) {
                    console.error('Error parsing response:', e);
                }
            };
        }
        
        function proxyRequest(url, method = 'GET', headers = {}, body = null) {
            return new Promise((resolve, reject) => {
                const id = requestId++;
                const request = {
                    id: id,
                    url: url,
                    method: method,
                    headers: headers,
                    body: body ? btoa(body) : null
                };
                
                pendingRequests.set(id, (response) => {
                    if (response.error) {
                        reject(new Error(response.error));
                    } else {
                        resolve(response);
                    }
                });
                
                ws.send(JSON.stringify(request));
                
                // Timeout after 30 seconds
                setTimeout(() => {
                    if (pendingRequests.has(id)) {
                        pendingRequests.delete(id);
                        reject(new Error('Request timeout'));
                    }
                }, 30000);
            });
        }
        
        async function loadPage(path) {
            try {
                status.textContent = 'Loading...';
                const response = await proxyRequest(path);
                
                if (response.contentType && response.contentType.includes('text/html')) {
                    // Decode base64 content
                    const html = atob(response.content);
                    
                    // Rewrite URLs in HTML to go through our proxy
                    const rewrittenHtml = rewriteHtml(html);
                    
                    // Create blob URL and load in iframe
                    const blob = new Blob([rewrittenHtml], { type: 'text/html' });
                    const url = URL.createObjectURL(blob);
                    frame.src = url;
                    
                    status.textContent = 'Loaded ✓';
                } else {
                    status.textContent = 'Error: Not HTML';
                }
            } catch (error) {
                console.error('Load error:', error);
                status.textContent = 'Error: ' + error.message;
            }
        }
        
        function rewriteHtml(html) {
            // Basic URL rewriting - make all links relative or intercept
            // This is simplified - a full implementation would need more robust parsing
            html = html.replace(/https:\\/\\/www\\.netflix\\.com/g, '');
            html = html.replace(/https:\\/\\/assets\\.nflxext\\.com/g, '/assets');
            
            // Inject script to intercept fetch/XHR
            const injectedScript = `
                <script>
                (function() {
                    // Intercept fetch
                    const originalFetch = window.fetch;
                    window.fetch = function(url, options = {}) {
                        console.log('[WS Proxy] Intercepting fetch:', url);
                        return window.parent.proxyFetch(url, options);
                    };
                    
                    // Intercept XHR
                    const originalXHR = XMLHttpRequest.prototype.open;
                    XMLHttpRequest.prototype.open = function(method, url, ...args) {
                        console.log('[WS Proxy] Intercepting XHR:', url);
                        // Let it pass for now - more complex to proxy
                        return originalXHR.call(this, method, url, ...args);
                    };
                })();
                </script>
            `;
            
            html = html.replace('</head>', injectedScript + '</head>');
            
            return html;
        }
        
        // Expose proxy function to iframe
        window.proxyFetch = async function(url, options) {
            try {
                const response = await proxyRequest(url, options.method || 'GET', options.headers, options.body);
                
                // Return a Response-like object
                return {
                    ok: response.status >= 200 && response.status < 300,
                    status: response.status,
                    statusText: response.statusText || 'OK',
                    headers: new Headers(response.headers || {}),
                    text: async () => atob(response.content),
                    json: async () => JSON.parse(atob(response.content)),
                    arrayBuffer: async () => {
                        const binary = atob(response.content);
                        const buffer = new ArrayBuffer(binary.length);
                        const view = new Uint8Array(buffer);
                        for (let i = 0; i < binary.length; i++) {
                            view[i] = binary.charCodeAt(i);
                        }
                        return buffer;
                    }
                };
            } catch (error) {
                console.error('[WS Proxy] Fetch error:', error);
                throw error;
            }
        };
        
        connect();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@sock.route('/ws')
def websocket(ws):
    print("[WS] Client connected")
    
    while True:
        try:
            message = ws.receive()
            if message is None:
                break
            
            request = json.loads(message)
            print(f"[WS] Request {request['id']}: {request['method']} {request['url']}")
            
            # Build full URL
            url = request['url']
            if not url.startswith('http'):
                url = TARGET_URL.rstrip('/') + ('/' if not url.startswith('/') else '') + url
            
            # Make the request
            try:
                headers = request.get('headers', {})
                headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                
                body = None
                if request.get('body'):
                    body = base64.b64decode(request['body'])
                
                resp = requests.request(
                    method=request['method'],
                    url=url,
                    headers=headers,
                    data=body,
                    timeout=10,
                    allow_redirects=True
                )
                
                # Encode response
                content_b64 = base64.b64encode(resp.content).decode('utf-8')
                
                response = {
                    'id': request['id'],
                    'status': resp.status_code,
                    'statusText': resp.reason,
                    'headers': dict(resp.headers),
                    'contentType': resp.headers.get('Content-Type', ''),
                    'content': content_b64
                }
                
                print(f"[WS] Response {request['id']}: {resp.status_code} ({len(resp.content)} bytes)")
                ws.send(json.dumps(response))
                
            except requests.exceptions.RequestException as e:
                print(f"[WS] Request error: {e}")
                ws.send(json.dumps({
                    'id': request['id'],
                    'error': str(e)
                }))
                
        except Exception as e:
            print(f"[WS] Error: {e}")
            break
    
    print("[WS] Client disconnected")

if __name__ == '__main__':
    print("Starting WebSocket Proxy on port 5001...")
    print("Access at: http://127.0.0.1:5001/")
    app.run(host='0.0.0.0', port=5001, debug=True)
