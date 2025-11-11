# CI/CD Setup for Master Proxy

This document explains the Continuous Integration and Continuous Deployment setup for Master Proxy.

## Overview

The project uses **GitHub Actions** for automated testing, code quality checks, security scans, and documentation deployment.

## Workflows

### 1. Test Workflow (`.github/workflows/test.yml`)

**Trigger:** Push to main/develop, Pull Requests, Manual dispatch

**Jobs:**

#### a) Test Job (Matrix)
- **Runs on:** Ubuntu Latest
- **Python versions:** 3.9, 3.10, 3.11
- **Steps:**
  1. Checkout code
  2. Setup Python (matrix version)
  3. Cache pip packages
  4. Install dependencies (flask, requests, flask-sock, simple-websocket)
  5. Verify master_proxy.py exists
  6. Check Python syntax
  7. Run unit tests (24 tests across 8 test classes)
  8. Optional pytest run
  9. Check for TODOs and hardcoded credentials

**Success criteria:** All tests pass on all Python versions

#### b) Lint Job
- **Runs on:** Ubuntu Latest
- **Python:** 3.11
- **Tools:** flake8, pylint
- **Steps:**
  1. Run flake8 (max line length 120, ignore E501/W503)
  2. Run pylint (disable some style warnings)
- **Note:** Continues on error (warnings don't fail build)

#### c) Security Job
- **Runs on:** Ubuntu Latest
- **Python:** 3.11
- **Tools:** bandit, safety
- **Steps:**
  1. Run Bandit security scan (high/medium severity)
  2. Check dependencies for vulnerabilities
- **Note:** Continues on error (for manual review)

#### d) Integration Job
- **Runs on:** Ubuntu Latest
- **Python:** 3.11
- **Steps:**
  1. Start master proxy in background
  2. Wait 5 seconds for startup
  3. Test homepage endpoint (curl)
  4. Test video proxy endpoint (curl with sample MP4)
  5. Test ultra mode endpoint
  6. Show proxy logs on failure
  7. Stop proxy
- **Success criteria:** All endpoints return expected responses

#### e) Docker Job
- **Runs on:** Ubuntu Latest
- **Steps:**
  1. Create Dockerfile dynamically
  2. Build Docker image (python:3.11-slim base)
  3. Run container on port 5000
  4. Test homepage endpoint
  5. Stop container
- **Success criteria:** Container builds and serves requests

#### f) Performance Job
- **Runs on:** Ubuntu Latest
- **Python:** 3.11
- **Steps:**
  1. Start proxy
  2. Benchmark homepage response time (10 requests)
  3. Measure total time
- **Output:** Response time metrics

### 2. Deploy Workflow (`.github/workflows/deploy.yml`)

**Trigger:** Push to main, Manual dispatch

**Permissions:** Pages write, ID token write

**Jobs:**

#### a) Build Docs Job
- **Runs on:** Ubuntu Latest
- **Steps:**
  1. Checkout code
  2. Generate HTML documentation site
  3. Upload as GitHub Pages artifact

#### b) Deploy Job
- **Runs on:** Ubuntu Latest
- **Depends on:** build-docs
- **Environment:** github-pages
- **Steps:**
  1. Deploy artifact to GitHub Pages

**Result:** Documentation available at `https://texasmadecode.github.io/proxy/`

## Local Testing

### Quick Test (Recommended)
```bash
./run_tests.sh
```

This script:
- Checks Python installation
- Validates syntax
- Installs dependencies
- Runs unit tests
- Performs smoke test
- Checks for common issues

### Manual Unit Tests
```bash
cd tests
python test_master_proxy.py
```

### Manual Integration Test
```bash
# Terminal 1
python3 master_proxy.py

# Terminal 2
curl http://localhost:5000/
curl -I "http://localhost:5000/video-proxy?url=https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
curl "http://localhost:5000/ultra/?url=https://example.com"
```

## Test Coverage

### Test Classes (24 tests total)

1. **TestHomepage** (3 tests)
   - Homepage loads
   - All modes listed
   - Stats displayed

2. **TestFlixHQMode** (3 tests)
   - Endpoint accessible
   - Interceptor injected
   - Banner present

3. **TestVideoProxy** (3 tests)
   - Requires url param
   - Streams MP4
   - CORS headers

4. **TestIframeProxy** (4 tests)
   - Requires url param
   - Fetches HTML
   - Interceptor injected
   - CORS headers

5. **TestUltraMode** (4 tests)
   - Works with url param
   - Shows banner
   - Injects blocker
   - Default target works

6. **TestStealthMode** (2 tests)
   - Endpoint accessible
   - Script injected

7. **TestUtilityFunctions** (3 tests)
   - 404 handling
   - HEAD request support
   - Large params handled

8. **TestPerformance** (2 tests)
   - Homepage loads quickly (<2s)
   - Concurrent requests work

### Expected Test Results

**Typical results:**
- ✅ 19-20 tests pass
- ⚠️ 3-4 tests may fail/skip (external dependencies)
- ❌ 1 test may error (timeout for slow external sites)

**Common failures (not bugs):**
- FlixHQ mode tests (if flixhq.to is down)
- Video streaming (if test video URL unavailable)
- Ultra mode (if target site times out)

## GitHub Actions Setup

### First-Time Setup

1. **Enable GitHub Actions**
   ```bash
   # In repository settings:
   Settings → Actions → General → Allow all actions
   ```

2. **Enable GitHub Pages**
   ```bash
   # In repository settings:
   Settings → Pages → Source: GitHub Actions
   ```

3. **Commit workflows**
   ```bash
   git add .github/workflows/
   git commit -m "Add CI/CD workflows"
   git push
   ```

4. **View results**
   - Go to "Actions" tab in GitHub
   - See workflow runs and results

### Adding Status Badges

Already added to README.md:
```markdown
[![CI Tests](https://github.com/texasmadecode/proxy/actions/workflows/test.yml/badge.svg)](...)
[![Deploy Docs](https://github.com/texasmadecode/proxy/actions/workflows/deploy.yml/badge.svg)](...)
```

## Workflow Triggers

### Automatic Triggers
- **Push to main** → Runs all workflows
- **Push to develop** → Runs test workflow
- **Pull Request** → Runs test workflow

### Manual Triggers
```bash
# Via GitHub UI:
Actions → Select workflow → Run workflow → Run

# Via GitHub CLI:
gh workflow run test.yml
gh workflow run deploy.yml
```

## Debugging Failed Workflows

### View Logs
1. Go to Actions tab
2. Click failed workflow run
3. Click failed job
4. Expand failed step
5. Review error messages

### Common Issues

**"Server not running"**
- Port 5000 may be in use
- Increase startup wait time
- Check server logs in workflow

**"Tests timed out"**
- External site unreachable
- Increase timeout in test config
- Expected for some tests

**"Dependencies failed to install"**
- Network issue in GitHub Actions
- Re-run workflow
- Check pip cache

**"Docker build failed"**
- Check Dockerfile syntax
- Verify base image available
- Check network connectivity

### Local Reproduction

To reproduce CI failures locally:
```bash
# Same environment as GitHub Actions
docker run -it -v $(pwd):/app python:3.11-slim bash
cd /app
pip install flask requests flask-sock simple-websocket
python3 tests/test_master_proxy.py
```

## CI/CD Best Practices

### Before Committing
1. Run `./run_tests.sh` locally
2. Fix any errors/warnings
3. Commit and push
4. Monitor GitHub Actions

### Pull Request Workflow
1. Create feature branch
2. Make changes
3. Run tests locally
4. Push to GitHub
5. Create pull request
6. Wait for CI checks
7. Fix any failures
8. Merge when green ✅

### Monitoring
- Watch Actions tab after each push
- Review failed tests immediately
- Don't ignore security warnings
- Keep dependencies updated

## Maintenance

### Update Dependencies
```bash
# Check for outdated packages
pip list --outdated

# Update requirements.txt
pip freeze > requirements.txt

# Test with new versions
./run_tests.sh
```

### Add New Tests
1. Edit `tests/test_master_proxy.py`
2. Add test method to appropriate class
3. Run locally: `python tests/test_master_proxy.py`
4. Commit and push
5. Verify passes in CI

### Disable a Workflow
```yaml
# Add to workflow file:
on:
  workflow_dispatch:  # Manual only
  # Remove: push, pull_request
```

## Performance Metrics

Typical CI run times:
- **Test job (per Python version):** 2-3 minutes
- **Lint job:** 30 seconds
- **Security job:** 1 minute
- **Integration job:** 1-2 minutes
- **Docker job:** 2-3 minutes
- **Performance job:** 1 minute
- **Total pipeline:** 5-8 minutes

## Security Considerations

### Secrets Management
- No secrets currently needed
- If adding: Use GitHub Secrets
- Never commit credentials

### Dependency Security
- `safety check` runs on every commit
- Review CVE warnings
- Update vulnerable packages promptly

### Code Security
- `bandit` scans for security issues
- Review high/medium severity findings
- Fix SQL injection, XSS, etc.

## Future Improvements

### Planned Enhancements
1. Add code coverage reporting (Codecov)
2. Add mutation testing (mutpy)
3. Add performance regression tests
4. Add end-to-end browser tests (Playwright)
5. Add multi-platform testing (Windows, macOS)
6. Add automatic dependency updates (Dependabot)

### Nice to Have
- Slack/Discord notifications
- Deployment to cloud (Heroku, Railway)
- Load testing (Locust)
- Visual regression testing
- API documentation generation

---

**Last Updated:** November 11, 2025  
**Maintained By:** texasmadecode  
**Questions?** Open an issue on GitHub
