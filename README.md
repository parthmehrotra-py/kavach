# Kavach

**Local-first PII review, redaction, and restoration for AI workflows**

Kavach is a Windows desktop application that helps reduce exposure of personal identifiers before you manually share text with an external AI service. It surfaces detection candidates for review, redacts only what you approve, and can restore placeholders in a reply using the active session. Detection may miss sensitive information, so review the redacted text before sharing it.

## How It Works

```
┌─────────────┐
│   You       │
│ (Windows)   │
└──────┬──────┘
       │ 1. Paste text/upload document
       ↓
┌─────────────────────────────────────┐
│  Kavach (localhost:8000)            │
│  ┌───────────────────────────────┐  │
│  │ Detection Pipeline            │  │
│  │  • Deterministic (Aadhaar,    │  │
│  │    PAN, phone, etc.)          │  │
│  │  • Optional contextual (NER)  │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │ Redaction Engine              │  │
│  │  • Create placeholders        │  │
│  │  • Store mapping (in-memory)  │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │ Restoration Engine            │  │
│  │  • Match exact tokens         │  │
│  │  • Restore original values    │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
       │ 2. Copy redacted text
       ↓
┌─────────────┐
│ External    │
│ AI Service  │◄─── You manually paste
│ (Cloud)     │     (Outside Kavach)
└──────┬──────┘
       │ 3. AI response
       ↓
    You manually paste back
       │
       ↓
┌─────────────────────────────────────┐
│  Kavach                             │
│  (Restores placeholders)            │
└─────────────────────────────────────┘
```

**Network Boundary:** Kavach binds only to 127.0.0.1 and makes no outbound requests. You manually copy/paste between Kavach and external services.

## Quick Start

### Requirements

- **OS**: Windows 11
- **Architecture**: Windows x64
- **Python**: 3.11, 3.12, or 3.13
- **Hardware**: CPU baseline (no GPU/NPU required)

### Setup

1. **Clone this repository**:
   ```powershell
   git clone <repository-url>
   cd "Snapdragon AI"
   ```

2. **Run setup** (installs dependencies in local `.venv`):
   ```powershell
   .\setup.ps1 -Dev
   ```

3. **Activate environment**:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

### Run

```powershell
python -m kavach.main
```

Then open your browser to: **http://127.0.0.1:8000/**

### Verify

Check that the app is running:
```powershell
# Health check
curl http://127.0.0.1:8000/api/v1/health

# Or in browser
http://127.0.0.1:8000/
```

## Two-Minute Demo (Synthetic Data Only)

**Scenario:** Redact synthetic identifiers from a sample message before manually sharing it with an AI service.

1. **Start Kavach** (see Run section above)

2. **Paste this synthetic text** in the UI:
   ```
   PAN: ABCDE1234F
   Phone: +91 9876543210
   Aadhaar: 2345-6789-0009
   ```
   These are synthetic test values.

3. **Click "Find personal details"** → Review the PAN, phone, and Aadhaar candidates.

4. **Approve the candidates** you want to redact.

5. **Click the enabled “Redact 3 approved details” button** → Get redacted text like:
   ```
   PAN: [[KAVACH:PAN:0001]]
   Phone: [[KAVACH:PHONE:0002]]
   Aadhaar: [[KAVACH:AADHAAR:0003]]
   ```

6. **Copy the session ID and redacted text** → Manually paste the text into your chosen external AI service.

7. **Example reply:**
   ```
   I reviewed the message. The PAN placeholder is [[KAVACH:PAN:0001]].
   ```

8. Paste the reply into Kavach’s “Restore the AI reply” section.

9. **Click "Restore original details"** → The active session replaces recognized placeholders.

10. Click **“Clear session and reset”** when done.

**Demo time:** ~2 minutes with all steps

## Supported Detection Types

### Deterministic (Always Available)
- **Aadhaar**: 12 digits, Verhoeff checksum validation
- **PAN**: AAAAA9999A format
- **IFSC**: Bank code format
- **UPI ID**: handle@provider
- **Indian phone numbers**: +91 prefix with validation
- **Indian PIN codes**: 6 digits with context
- **Account numbers**: Pattern with context keywords

### Contextual (Optional)
- **Person names**: Via spaCy NER (if installed)
- **Addresses/Locations**: Via spaCy NER (if installed)

**Note:** Contextual detection requires optional spaCy model installation. See [models/README.md](models/README.md).

## Model Provenance

### OCR (RapidOCR)
- **Library**: rapidocr-onnxruntime 1.2.3
- **Models**: PaddleOCR v3 (bundled, ~13MB)
- **License**: Apache 2.0 (library), Apache 2.0 (models)
- **Source**: https://github.com/RapidAI/RapidOCR
- **Runtime**: CPU (ONNX Runtime)

### Contextual NER (Optional)
- **Library**: spaCy 3.8.2
- **Model**: en_core_web_sm (if installed)
- **License**: MIT (spaCy), CC BY-SA 4.0 (model)
- **Source**: https://spacy.io/models/en#en_core_web_sm
- **Size**: ~12MB download
- **Installation**: `pip install -e ".[contextual]"` then `python -m spacy download en_core_web_sm`

**No models are committed to this repository.**

## Verified Hardware Table

| Target | Architecture | CPU baseline | Snapdragon NPU | Evidence |
|--------|--------------|--------------|----------------|----------|
| Windows development machine | x64 | Tested | Not applicable | Local development run (2026-09-30) |
| HP Snapdragon target | ARM64 | Not tested | Unverified | No device test yet |

**Legend:**
- ✅ Tested and working
- ❌ Not available/detected on this hardware
- ❓ Unverified (not tested)
- N/A: Not applicable to this hardware

**ARM64/Snapdragon status:** No HP Snapdragon device was available for verification. Compatibility and NPU acceleration remain **unverified** until tested on that hardware.

## Troubleshooting

### Setup Script Fails

**Issue:** Python version not supported
```
Error: Python 3.11 or newer is required.
```
**Fix:** Install Python 3.11, 3.12, or 3.13 from python.org. Other versions are outside the project's declared range.

**Issue:** Virtual environment creation fails
```
Error: Failed to create virtual environment.
```
**Fix:** Ensure `python -m venv` works. Try: `python -m ensurepip --upgrade`

### App Won't Start

**Issue:** Port 8000 already in use
```
Error: [Errno 10048] Address already in use
```
**Fix:** Stop other services on port 8000 or change port in `src/kavach/config.py`

**Issue:** Loopback validation failed
```
Error: Kavach must bind to a loopback IP address
```
**Fix:** Don't modify `settings.host`. Keep it as `127.0.0.1`.

### Dependencies

**Issue:** RapidOCR installation fails
```
Error: Failed to build wheel for rapidocr-onnxruntime
```
**Fix:** This is usually a Python 3.13+ compatibility issue. Try Python 3.11 or 3.12.

**Issue:** spaCy model not found
```
contextual_model_status: "model 'en_core_web_sm' not found"
```
**Fix:** This is expected if you haven't installed the optional model. The app works without it. To install:
```powershell
pip install -e ".[contextual]"
python -m spacy download en_core_web_sm
```

### Runtime Issues

**Issue:** Session not found after restore
```
Error: Session is missing or expired
```
**Fix:** Sessions expire after 30 minutes. Complete the workflow within the TTL or increase `session_ttl_seconds` in config.

## Development

### Quality Checks

```powershell
# Linting
ruff check .

# Format check
ruff format --check .

# Type checking
mypy src
```

### Run Focused Tests

```powershell
# All tests
pytest

# Specific phase
pytest tests/test_hardware.py -v

# With coverage
pytest --cov=src/kavach
```

## Limitations

### Functional
- Single-user, localhost-only
- Manual copy/paste workflow (no AI integration)
- No persistence (sessions are in-memory only)
- India-focused detection patterns

### Technical
- Windows x64 CPU baseline is the only verified runtime path
- ARM64/Snapdragon compatibility and acceleration are unverified
- Contextual model requires separate installation
- No GPU/NPU acceleration (CPU baseline only)

### Not Included
- Cloud API integration
- Mobile apps or browser extensions
- Multi-user or multi-device support
- Real-time collaboration
- Built-in AI models or chat interface

## Privacy & Security

**Local-First Design:**
- All processing happens on your device
- No telemetry or analytics
- No accounts or authentication
- Session data stored in RAM only
- Server binds only to 127.0.0.1 (loopback)

**Threat Model:**
- Kavach reduces exposure by replacing user-approved candidates before manual sharing; detection can miss sensitive information
- Kavach does not protect against local attacks or malware
- Localhost is not an authentication boundary
- You are responsible for securing your device

## License

[To be determined]

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for complete technical blueprint, implementation roadmap, and product contract.

## Project Status

Kavach is an early local prototype. The Windows x64 CPU path has been exercised. The setup check used the existing development environment; clean-machine setup and ARM64/Snapdragon compatibility have not been verified. Optional contextual model availability depends on a separate local installation.
