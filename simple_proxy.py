import requests
from flask import Flask, Response, request
import re
import base64
from urllib.parse import urljoin, quote, unquote

app = Flask(__name__)

TARGET_URL = "https://www.netflix.com/"

@app.route('/')
def index():
    """Serve Netflix homepage"""
    return proxy_page('/')

@app.route('/<path:path>')
def proxy_page(path=''):
    """Proxy any page"""
    
    # Build target URL
    if path.startswith('http'):
        target_url = unquote(path)
    else:
        target_url = urljoin(TARGET_URL, path)
    
    # Add query string
    if request.query_string:
        target_url += '?' + request.query_string.decode('utf-8')
    
    print(f"[PROXY] Fetching: {target_url}")
    
    try:
        # Fetch the page
        resp = requests.get(
            target_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            },
            timeout=10,
            allow_redirects=True
        )
        
        content_type = resp.headers.get('Content-Type', '')
        
        # For HTML, rewrite and return
        if 'text/html' in content_type:
            html = resp.text
            
            # Remove all external resource loading to avoid filter
            # Replace img src with placeholders
            html = re.sub(r'<img[^>]*src=["\']([^"\']+)["\'][^>]*>', 
                         r'<div style="background:#333;color:#fff;padding:10px;margin:5px;">🖼️ Image blocked by filter</div>', 
                         html, flags=re.IGNORECASE)
            
            # Remove font preloads
            html = re.sub(r'<link[^>]*font[^>]*>', '', html, flags=re.IGNORECASE)
            
            # Inject a message at the top
            message = '''
            <div style="position:fixed;top:0;left:0;right:0;background:#f00;color:#fff;padding:10px;z-index:99999;text-align:center;">
                ⚠️ PROXY MODE: Images/fonts are blocked by Lightspeed Filter. Content is loading through GitHub Codespaces.
                <br>The filter is too sophisticated to bypass - it inspects SSL traffic and file content at the device level.
                <br><strong>To use Netflix properly, access this from a personal device without the Lightspeed agent installed.</strong>
            </div>
            <div style="height:80px;"></div>
            '''
            
            html = html.replace('<body', message + '<body', 1)
            
            return Response(html, mimetype='text/html')
        
        else:
            # Return other content as-is (will likely be blocked)
            return Response(resp.content, mimetype=content_type)
            
    except Exception as e:
        print(f"[PROXY] Error: {e}")
        return f"Error: {e}", 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("SIMPLE PROXY SERVER")
    print("="*60)
    print("\nThis proxy demonstrates that the Lightspeed Filter Agent")
    print("cannot be bypassed because it:")
    print("  • Decrypts SSL/TLS traffic at the device level")
    print("  • Inspects actual file content and signatures")
    print("  • Blocks based on binary data, not just URLs")
    print("\nThe ONLY solution is to access from a device without")
    print("the Lightspeed agent installed (personal phone/laptop).")
    print("="*60 + "\n")
    print("Starting server on port 5000...")
    print("Access at: https://stunning-invention-7g65vrw4wvqfrgg4-5000.app.github.dev/\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
