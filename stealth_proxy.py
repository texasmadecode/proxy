import requests
import base64
import json
import hashlib
from flask import Flask, Response, request, jsonify
from urllib.parse import urljoin, quote, unquote
import re

app = Flask(__name__)

TARGET_URL = "https://www.netflix.com/"
resource_cache = {}

@app.route('/api/resource/<resource_id>')
def get_resource(resource_id):
    """
    Serve resources as JSON (looks like API data to filter, not images)
    """
    if resource_id not in resource_cache:
        return jsonify({'error': 'not found'}), 404
    
    url = resource_cache[resource_id]
    print(f"[API] Fetching resource: {url[:80]}...")
    
    try:
        resp = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if resp.status_code != 200:
            return jsonify({'error': 'fetch failed'}), resp.status_code
        
        # Encode as base64 and wrap in JSON
        # This looks like API data, not an image file
        data = {
            'type': 'resource',
            'encoding': 'base64',
            'data': base64.b64encode(resp.content).decode('utf-8'),
            'mime': resp.headers.get('Content-Type', 'application/octet-stream'),
            'size': len(resp.content)
        }
        
        print(f"[API] Served {len(resp.content)} bytes as JSON")
        
        # Return as JSON with text/plain to avoid any image detection
        response = Response(
            json.dumps(data),
            mimetype='text/plain'  # Looks like text, not JSON or images
        )
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
        
    except Exception as e:
        print(f"[API] Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    return proxy_page('/')

@app.route('/<path:path>')
def proxy_page(path=''):
    """Proxy and inject stealth loader"""
    
    if path.startswith('api/'):
        return "Invalid path", 404
    
    # Build target URL
    target_url = urljoin(TARGET_URL, path)
    if request.query_string:
        target_url += '?' + request.query_string.decode('utf-8')
    
    print(f"[PROXY] Fetching: {target_url}")
    
    try:
        resp = requests.get(
            target_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            timeout=10,
            allow_redirects=True
        )
        
        content_type = resp.headers.get('Content-Type', '')
        
        if 'text/html' in content_type:
            html = resp.text
            
            # Inject stealth resource loader at the beginning
            stealth_script = '''
<script>
(function() {
    console.log('[Stealth] Initializing...');
    
    const resourceCache = new Map();
    const pendingLoads = new Map();
    
    // Function to load resource via API
    async function loadResource(url) {
        if (resourceCache.has(url)) {
            return resourceCache.get(url);
        }
        
        if (pendingLoads.has(url)) {
            return pendingLoads.get(url);
        }
        
        const loadPromise = (async () => {
            try {
                // Generate resource ID
                const encoder = new TextEncoder();
                const data = encoder.encode(url);
                const hashBuffer = await crypto.subtle.digest('SHA-256', data);
                const hashArray = Array.from(new Uint8Array(hashBuffer));
                const resourceId = hashArray.map(b => b.toString(16).padStart(2, '0')).join('').substring(0, 16);
                
                // Register resource server-side first (and wait for it)
                await fetch('/register?id=' + resourceId + '&url=' + encodeURIComponent(url), {
                    method: 'GET',
                    cache: 'no-cache'
                });
                
                console.log('[Stealth] Registered:', resourceId, 'for', url.substring(0, 50) + '...');
                
                // Now fetch as "text" API data
                const response = await fetch('/api/resource/' + resourceId);
                const text = await response.text();
                const json = JSON.parse(text);
                
                if (json.error) {
                    throw new Error(json.error);
                }
                
                // Decode base64
                const binaryString = atob(json.data);
                const bytes = new Uint8Array(binaryString.length);
                for (let i = 0; i < binaryString.length; i++) {
                    bytes[i] = binaryString.charCodeAt(i);
                }
                
                // Create blob URL
                const blob = new Blob([bytes], { type: json.mime });
                const blobUrl = URL.createObjectURL(blob);
                
                resourceCache.set(url, blobUrl);
                console.log('[Stealth] Loaded:', url.substring(0, 60) + '...');
                
                return blobUrl;
                
            } catch (error) {
                console.error('[Stealth] Load failed:', url, error);
                return null;
            }
        })();
        
        pendingLoads.set(url, loadPromise);
        const result = await loadPromise;
        pendingLoads.delete(url);
        
        return result;
    }
    
    // Intercept image loading
    const originalImage = window.Image;
    window.Image = function() {
        const img = new originalImage();
        const originalSet = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src').set;
        
        Object.defineProperty(img, 'src', {
            set: function(value) {
                if (value && (value.startsWith('http') || value.startsWith('//'))) {
                    const fullUrl = value.startsWith('//') ? 'https:' + value : value;
                    loadResource(fullUrl).then(blobUrl => {
                        if (blobUrl) {
                            originalSet.call(img, blobUrl);
                        } else {
                            originalSet.call(img, value);
                        }
                    });
                } else {
                    originalSet.call(img, value);
                }
            },
            get: function() {
                return Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src').get.call(this);
            }
        });
        
        return img;
    };
    
    // Intercept existing images
    function processImages() {
        const images = document.querySelectorAll('img');
        images.forEach(img => {
            const src = img.getAttribute('src');
            if (src && (src.startsWith('http') || src.startsWith('//'))) {
                const fullUrl = src.startsWith('//') ? 'https:' + src : src;
                console.log('[Stealth] Processing image:', fullUrl.substring(0, 60) + '...');
                loadResource(fullUrl).then(blobUrl => {
                    if (blobUrl) {
                        img.src = blobUrl;
                    }
                });
            }
        });
    }
    
    // Process images when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', processImages);
    } else {
        processImages();
    }
    
    // Watch for new images
    const observer = new MutationObserver((mutations) => {
        mutations.forEach(mutation => {
            mutation.addedNodes.forEach(node => {
                if (node.tagName === 'IMG') {
                    const src = node.getAttribute('src');
                    if (src && (src.startsWith('http') || src.startsWith('//'))) {
                        const fullUrl = src.startsWith('//') ? 'https:' + src : src;
                        loadResource(fullUrl).then(blobUrl => {
                            if (blobUrl) {
                                node.src = blobUrl;
                            }
                        });
                    }
                }
            });
        });
    });
    
    observer.observe(document.body || document.documentElement, {
        childList: true,
        subtree: true
    });
    
    console.log('[Stealth] Ready!');
})();
</script>
'''
            
            html = html.replace('<head>', '<head>' + stealth_script, 1)
            
            # Remove external resources that would be blocked
            html = re.sub(r'<link[^>]*font[^>]*>', '', html, flags=re.IGNORECASE)
            
            return Response(html, mimetype='text/html')
        
        else:
            # Pass through other content
            return Response(resp.content, mimetype=content_type)
            
    except Exception as e:
        print(f"[PROXY] Error: {e}")
        return f"Error: {e}", 500

@app.route('/register')
def register_resource():
    """Register a resource URL mapping"""
    resource_id = request.args.get('id')
    url = request.args.get('url')
    
    if resource_id and url:
        resource_cache[resource_id] = unquote(url)
        print(f"[REGISTER] {resource_id} -> {url[:60]}...")
    
    # Return 1x1 transparent pixel
    pixel = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')
    return Response(pixel, mimetype='image/gif')

if __name__ == '__main__':
    print("\n" + "="*70)
    print("STEALTH PROXY - Resources loaded as 'text/plain' JSON API data")
    print("="*70)
    print("\nStrategy:")
    print("  • Images fetched via /api/resource/<id> (looks like API, not images)")
    print("  • Data returned as JSON wrapped in text/plain mimetype")
    print("  • JavaScript decodes base64 and creates blob URLs client-side")
    print("  • Filter sees: text API calls, not image files")
    print("="*70 + "\n")
    print("Starting server on port 5000...\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
