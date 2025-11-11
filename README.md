# 🚀 Master Proxy - Multi-Mode Web Bypass System

A comprehensive proxy server combining **6 successful bypass strategies** for evading device-level web filters.

## 🎯 Quick Start

```bash
python3 master_proxy.py
```

Then open: **http://localhost:5000**

## 📖 What's Inside

This repository contains:

- **`master_proxy.py`** ⭐ — **USE THIS!** Consolidated multi-mode proxy with 6 strategies
- `flixhq_proxy.py` — Original FlixHQ streaming proxy (now integrated into master)
- `vpn_tunnel.py` — Original VPN tunnel (now integrated into master)
- `ultra_proxy.py` — Original ultra-embed proxy (now integrated into master)
- `nuclear_proxy.py` — Original image-embedding proxy (now integrated into master)
- `stealth_proxy.py` — Original stealth proxy (now integrated into master)

## 🎬 Proxy Modes

1. **🎬 FlixHQ Streaming** — Aggressive video/iframe interception for streaming sites
2. **📹 Video Proxy** — Server-side video streaming (MP4, HLS, DASH)
3. **🖼️ Iframe Proxy** — Recursive iframe proxying with interception
4. **⚡ Ultra Mode** — Complete server-side page assembly (inline everything)
5. **🔒 VPN Tunnel** — Encrypted WebSocket tunnel (VPN-like routing)
6. **🥷 Stealth Mode** — Resources disguised as JSON text/plain

## ✅ What Works

- ✅ Free streaming sites (FlixHQ, etc.)
- ✅ Domain blocking bypass
- ✅ Video streaming (non-DRM)
- ✅ Image/font blocking bypass
- ✅ Content-type filtering bypass

## ❌ What Doesn't Work

- ❌ DRM content (Netflix, Disney+, HBO) — Widevine DRM cannot be bypassed
- ❌ Kernel-level filters — OS-level enforcement beyond proxy's reach
- ❌ Certificate-pinned apps — Native apps with cert pinning

## 📚 Documentation

- **`MASTER_PROXY_README.md`** — Comprehensive documentation (usage, modes, troubleshooting, technical deep dive)
- **`QUICKSTART.txt`** — Quick reference card for all modes

## 🧪 Quick Test

```bash
# Start server
python3 master_proxy.py

# Test homepage
curl http://localhost:5000/

# Test video proxy
curl -I "http://localhost:5000/video-proxy?url=https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"

# Test FlixHQ mode
open http://localhost:5000/flixhq/
```

## 🛠️ Requirements

```bash
pip3 install flask requests flask-sock simple-websocket
```

(Auto-installs on first run if missing)

## ⚠️ Disclaimer

**Educational use only.** Respect Terms of Service, copyright laws, and school/workplace policies. No warranty provided. Use at your own risk.

## 🎓 How It Works

Combines multiple bypass strategies:
- **Domain hiding** — Server fetches blocked sites, browser only sees proxy domain
- **Resource inlining** — Everything embedded as data URIs (zero external requests)
- **Content disguise** — Resources served as JSON text to evade content-type filters
- **Encrypted tunnel** — WebSocket VPN-style routing hides all destinations
- **Streaming relay** — Server re-streams video chunks to bypass domain blocking

Filter sees: Requests to your proxy (allowed)  
Filter doesn't see: Blocked destinations (hidden in query params or encrypted)

---

**Read `MASTER_PROXY_README.md` for full documentation!**