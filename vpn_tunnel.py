#!/usr/bin/env python3
"""
Simple VPN Tunnel Proxy - Encrypted WebSocket
"""
from flask import Flask, request, Response
from flask_sock import Sock
import requests
import base64
import json

app = Flask(__name__)
sock = Sock(app)

TARGET_URL = "https://www.netflix.com/"

# Simple XOR encryption
def encrypt_data(data, key=0x5A):
    if isinstance(data, str):
        data = data.encode('utf-8')
    return bytes([b ^ key for b in data])

def decrypt_data(data, key=0x5A):
    return bytes([b ^ key for b in data])

# WebSocket tunnel
@sock.route('/tunnel')
def tunnel(ws):
    print("[TUNNEL] Client connected")
    
    while True:
        try:
            encrypted_msg = ws.receive()
            if not encrypted_msg:
                break
            
            decrypted = decrypt_data(base64.b64decode(encrypted_msg))
            request_data = json.loads(decrypted.decode('utf-8'))
            
            url = request_data.get('url')
            method = request_data.get('method', 'GET')
            
            print(f"[TUNNEL] {method} {url}")
            
            try:
                resp = requests.get(url, timeout=15, allow_redirects=True, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                response_data = {
                    'status': resp.status_code,
                    'headers': dict(resp.headers),
                    'body': base64.b64encode(resp.content).decode('utf-8'),
                    'url': resp.url,
                    'content_type': resp.headers.get('content-type', 'text/html')
                }
                
                print(f"[TUNNEL] ✓ {resp.status_code} Content-Type: {resp.headers.get('content-type', 'MISSING')}")
                
                response_json = json.dumps(response_data)
                encrypted_response = base64.b64encode(encrypt_data(response_json)).decode('utf-8')
                ws.send(encrypted_response)
                
            except Exception as e:
                print(f"[TUNNEL] Error: {e}")
                
        except Exception as e:
            print(f"[TUNNEL] Connection error: {e}")
            break
    
    print("[TUNNEL] Disconnected")

@app.route('/')
def index():
    html = open('/workspaces/proxy/vpn_client.html').read()
    return Response(html, mimetype='text/html')

if __name__ == '__main__':
    import subprocess
    import sys
    
    print("\n🔒 VPN TUNNEL PROXY\n")
    print("Installing flask-sock...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "flask-sock"])
    
    print("\nStarting server on port 5000...\n")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
