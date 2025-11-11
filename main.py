import requests
import os
import logging
import sys
import base64
from flask import Flask, request, Response, abort, send_from_directory
from urllib.parse import urljoin, urlparse

app = Flask(__name__)

# Simple in-memory cache for fonts and images
font_cache = {}
image_cache = {}

# Configure logging to output to console and to a file so we can inspect logs
log_file = os.path.join(os.path.dirname(__file__), 'proxy.log')
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# --- Configuration ---
# Set the target website you want to proxy. 
# IMPORTANT: Include the scheme (http/https) and a trailing slash if necessary.
TARGET_URL = "https://www.netflix.com/" 
# ---------------------

# Normalize TARGET_URL so missing scheme/trailing slash don't break urljoin/redirect logic
if not TARGET_URL.startswith(("http://", "https://")):
    TARGET_URL = "https://" + TARGET_URL
if not TARGET_URL.endswith("/"):
    TARGET_URL += "/"
app.logger.info(f"Using TARGET_URL={TARGET_URL}")

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
def proxy(path):
    # Handle special /proxy route for external URLs
    if path == 'proxy' and request.args.get('url'):
        external_url = request.args.get('url')
        print(f"[PROXY] Proxying external URL: {external_url}", flush=True)
        target_url = external_url
    else:
        # Construct the full target URL
        target_url = urljoin(TARGET_URL, path)
    
    # Handle query parameters (only if not already using ?url=)
    if request.query_string and not request.args.get('url'):
        target_url = f"{target_url}?{request.query_string.decode('utf-8')}"
    
    # log the proxied target for debugging
    print(f"[PROXY] Proxying {request.method} {request.path} -> {target_url}", flush=True)
    print(f"[PROXY] Incoming host: {request.host}  url_root: {request.url_root}", flush=True)
    app.logger.info(f"Proxying {request.method} {request.path} -> {target_url}")
    app.logger.info(f"Incoming host: {request.host}  url_root: {request.url_root}")
    
    # Prepare headers for the request to the target site
    # Exclude headers that might cause issues (e.g., Host, Origin, Referer)
    headers = {key: value for key, value in request.headers.items() if key.lower() not in ['host', 'origin', 'referer', 'cookie']}
    
    # Add a realistic User-Agent if none exists
    if 'User-Agent' not in headers and 'user-agent' not in headers:
        headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    
    print(f"[PROXY] Request headers: {headers}", flush=True)
    
    try:
        # Make the request to the target website (streamed, with a timeout)
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            stream=True,
            timeout=10
        )

        # Log upstream response headers for debugging
        print(f"[PROXY] Upstream headers: {dict(resp.headers)}", flush=True)
        print(f"[PROXY] Upstream raw Location: {resp.headers.get('Location')}", flush=True)
        app.logger.info(f"Upstream headers: {dict(resp.headers)}")
        app.logger.info(f"Upstream raw Location: {resp.headers.get('Location')}")
        
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        
        # Get proxy origin - handle X-Forwarded headers for Codespaces/reverse proxies
        if request.headers.get('X-Forwarded-Host'):
            # We're behind a proxy (like Codespaces port forwarding)
            forwarded_proto = request.headers.get('X-Forwarded-Proto', 'https')
            forwarded_host = request.headers.get('X-Forwarded-Host')
            proxy_origin = f"{forwarded_proto}://{forwarded_host}"
            print(f"[PROXY] Using X-Forwarded headers: {proxy_origin}", flush=True)
        else:
            proxy_origin = request.url_root.rstrip('/')
        
        print(f"[PROXY] Proxy origin: {proxy_origin}", flush=True)

        # If HTML, read and rewrite body so links to the target go through the proxy
        content_type = resp.headers.get('Content-Type', '')
        if 'text/html' in content_type.lower():
            try:
                # grab full content (not streaming) so we can rewrite URLs
                raw = resp.content
                enc = resp.encoding or 'utf-8'
                text = raw.decode(enc, errors='ignore')
                
                # Log first 500 chars to see what we're getting
                print(f"[PROXY] HTML preview (first 500 chars): {text[:500]}", flush=True)
                
                # Rewrite ALL absolute URLs to go through the proxy
                # This includes Netflix CDN domains (nflxso.net, nflxext.com, etc.)
                import re
                from urllib.parse import quote
                
                # Replace absolute https:// and http:// URLs with proxy path
                def rewrite_url(match):
                    full_url = match.group(0)
                    # Extract the URL (remove quotes if present)
                    url = full_url.split('=', 1)[1].strip('"').strip("'")
                    if url.startswith('http'):
                        # Skip if URL already points to our proxy
                        if '/proxy?url=' in url or url.startswith(proxy_origin):
                            return full_url
                        # Encode the full URL as a query parameter to proxy it
                        return f'{match.group(1)}="{proxy_origin}/proxy?url={quote(url)}"'
                    return full_url
                
                # Replace URLs in href, src, srcset, content attributes
                text = re.sub(r'(href|src|content)=["\']https?://[^"\']+["\']', rewrite_url, text)
                
                # Also replace scheme-less URLs (//domain.com/path)
                def rewrite_schemeless(match):
                    url = match.group(0).split('=', 1)[1].strip('"').strip("'")
                    if '/proxy?url=' in url:
                        return match.group(0)
                    full_url = "https:" + url
                    return f'{match.group(1)}="{proxy_origin}/proxy?url={quote(full_url)}"'
                
                text = re.sub(r'(href|src|content)=["\']//[^"\']+["\']', rewrite_schemeless, text)
                
                # Remove <link preload> for fonts since they trigger the filter
                # Fonts will load later via CSS with embedded data URIs
                text = re.sub(r'<link[^>]*rel=["\']preload["\'][^>]*as=["\']font["\'][^>]*>', '', text, flags=re.IGNORECASE)
                text = re.sub(r'<link[^>]*as=["\']font["\'][^>]*rel=["\']preload["\'][^>]*>', '', text, flags=re.IGNORECASE)
                
                # IMPORTANT: Also rewrite URLs inside inline <script> tags
                # Replace 'https://domain.com/path' with proxy URLs in JavaScript strings
                def rewrite_js_url(match):
                    url = match.group(1)
                    if '/proxy?url=' in url or url.startswith(proxy_origin):
                        return match.group(0)
                    return f"'{proxy_origin}/proxy?url={quote(url)}'"
                
                text = re.sub(r"'(https?://[^']+)'", rewrite_js_url, text)
                text = re.sub(r'"(https?://[^"]+)"', lambda m: f'"{proxy_origin}/proxy?url={quote(m.group(1))}"' if '/proxy?url=' not in m.group(1) and not m.group(1).startswith(proxy_origin) else m.group(0), text)
                
                body = text.encode(enc)
                response = Response(body, status=resp.status_code, mimetype='text/html')
            except Exception as e:
                app.logger.error(f"HTML rewrite failed: {e}")
                # fallback to streaming if rewrite fails
                def generate():
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            yield chunk
                response = Response(generate(), status=resp.status_code)
        elif 'text/css' in content_type.lower() or 'text/javascript' in content_type.lower():
            # Rewrite CSS and JS files too (for url() in CSS and fetch/XHR in JS)
            try:
                raw = resp.content
                enc = resp.encoding or 'utf-8'
                text = raw.decode(enc, errors='ignore')
                
                import re
                from urllib.parse import quote
                
                # For CSS: convert fonts to data URIs to bypass filter
                if 'text/css' in content_type.lower():
                    def rewrite_css_url(match):
                        url = match.group(1).strip('"').strip("'")
                        if '/proxy?url=' in url or proxy_origin in url:
                            return match.group(0)
                        
                        full_url = None
                        if url.startswith('http'):
                            full_url = url
                        elif url.startswith('//'):
                            full_url = "https:" + url
                        
                        # Convert fonts to base64 data URIs
                        if full_url and any(ext in full_url.lower() for ext in ['.woff2', '.woff', '.ttf', '.eot', '.otf']):
                            try:
                                # Check cache first
                                if full_url in font_cache:
                                    return f'url({font_cache[full_url]})'
                                
                                # Fetch the font
                                print(f"[PROXY] Fetching font for embedding: {full_url}", flush=True)
                                font_resp = requests.get(full_url, timeout=10)
                                if font_resp.status_code == 200:
                                    # Determine MIME type
                                    mime_type = 'font/woff2' if '.woff2' in full_url else 'font/woff' if '.woff' in full_url else 'font/ttf'
                                    # Convert to base64
                                    font_b64 = base64.b64encode(font_resp.content).decode('utf-8')
                                    data_uri = f'"data:{mime_type};base64,{font_b64}"'
                                    # Cache it
                                    font_cache[full_url] = data_uri
                                    print(f"[PROXY] Embedded font: {full_url[:50]}... ({len(font_resp.content)} bytes)", flush=True)
                                    return f'url({data_uri})'
                            except Exception as e:
                                print(f"[PROXY] Failed to embed font {full_url}: {e}", flush=True)
                                # Fallback to proxy URL
                                return f'url("{proxy_origin}/proxy?url={quote(full_url)}")'
                        
                        # Non-font resources use proxy URL
                        if full_url:
                            return f'url("{proxy_origin}/proxy?url={quote(full_url)}")'
                        return match.group(0)
                    
                    text = re.sub(r'url\(["\']?([^)]+)["\']?\)', rewrite_css_url, text)
                else:
                    # JavaScript: just rewrite URLs normally
                    text = re.sub(r"'(https?://[^']+)'", lambda m: f"'{proxy_origin}/proxy?url={quote(m.group(1))}'" if '/proxy?url=' not in m.group(1) and proxy_origin not in m.group(1) else m.group(0), text)
                    text = re.sub(r'"(https?://[^"]+)"', lambda m: f'"{proxy_origin}/proxy?url={quote(m.group(1))}"' if '/proxy?url=' not in m.group(1) and proxy_origin not in m.group(1) else m.group(0), text)
                
                body = text.encode(enc)
                response = Response(body, status=resp.status_code, mimetype=content_type)
            except Exception as e:
                app.logger.error(f"CSS/JS rewrite failed: {e}")
                def generate():
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            yield chunk
                response = Response(generate(), status=resp.status_code)
        else:
            # For images and other binary content, serve directly with proper headers
            # The key is that they come from our proxy domain, not external domains
            def generate():
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            response = Response(generate(), status=resp.status_code)

        # Copy and possibly rewrite headers (force Location -> proxy)
        target_parsed = urlparse(TARGET_URL)
        target_netloc = target_parsed.netloc
        
        # Check if this is an image - if so, obscure it from the filter
        is_image = any(img_type in content_type.lower() for img_type in ['image/', 'jpeg', 'jpg', 'png', 'gif', 'webp', 'svg'])
        
        for key, value in resp.headers.items():
            if key.lower() in excluded_headers:
                continue
            
            # Disguise images as generic binary data to bypass content filter
            if is_image and key.lower() == 'content-type':
                value = 'application/octet-stream'
                print(f"[PROXY] Masking image content-type as octet-stream", flush=True)

            if key.lower() == 'location' and value:
                try:
                    loc = urlparse(value)
                    print(f"[PROXY] Original Location header: {value}", flush=True)
                    app.logger.info(f"Original Location header: {value}")
                    
                    # Only rewrite if redirect points to our TARGET domain
                    if loc.netloc == target_netloc or (not loc.netloc and value.startswith('/')):
                        # Rewrite to go through proxy
                        if loc.netloc:
                            # Absolute URL pointing to target domain
                            path_q = (loc.path or '/') + ('?' + loc.query if loc.query else '')
                            value = proxy_origin + path_q
                        else:
                            # Relative URL
                            value = proxy_origin + value
                        print(f"[PROXY] Rewriting Location header to: {value}", flush=True)
                        app.logger.info(f"Rewriting Location header to: {value}")
                    else:
                        # Different domain - let it redirect naturally
                        print(f"[PROXY] Location points to different domain ({loc.netloc}), not rewriting", flush=True)
                        app.logger.info(f"Location points to different domain ({loc.netloc}), not rewriting")
                except Exception as e:
                    app.logger.error(f"Error rewriting Location: {e}")

            response.headers[key] = value
        
        # Add CORS headers to allow cross-origin resource loading
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = '*'

        app.logger.info(f"Upstream {target_url} responded {resp.status_code}")
        return response

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error fetching target URL: {e}")
        abort(502, description="Bad Gateway or target site is unreachable")

# Serve a local content.js (so service worker file is present in the dev container)
@app.route('/content.js')
def serve_content_js():
    app.logger.info("Serving local /content.js")
    static_dir = os.path.join(app.root_path, 'static')
    return send_from_directory(static_dir, 'content.js')

if __name__ == '__main__':
    # Run the Flask app on localhost, port 5000
    # You can access the proxy at http://127.0.0.1:5000/
    app.run(debug=True, port=5000)
