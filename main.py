import requests
import os
from flask import Flask, request, Response, abort, send_from_directory
from urllib.parse import urljoin, urlparse

app = Flask(__name__)

# --- Configuration ---
# Set the target website you want to proxy. 
# IMPORTANT: Include the scheme (http/https) and a trailing slash if necessary.
TARGET_URL = "https://example.com/" 
# ---------------------

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
def proxy(path):
    # Construct the full target URL
    target_url = urljoin(TARGET_URL, path)
    
    # Handle query parameters
    if request.query_string:
        target_url = f"{target_url}?{request.query_string.decode('utf-8')}"
    
    # log the proxied target for debugging
    app.logger.info(f"Proxying {request.method} {request.path} -> {target_url}")
    
    # Prepare headers for the request to the target site
    # Exclude headers that might cause issues (e.g., Host, Origin, Referer)
    headers = {key: value for key, value in request.headers.items() if key.lower() not in ['host', 'origin', 'referer', 'cookie']}
    
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

        # Stream the response content back to the client
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        def generate():
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

        response = Response(generate(), status=resp.status_code)
        
        # Copy relevant headers
        for key, value in resp.headers.items():
            if key.lower() in excluded_headers:
                continue
            # Rewrite Location headers that point to the target so redirects go through the proxy
            if key.lower() == 'location' and value.startswith(TARGET_URL):
                # replace target origin with this proxy's origin
                value = value.replace(TARGET_URL.rstrip('/'), request.url_root.rstrip('/'), 1)
            response.headers[key] = value

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
