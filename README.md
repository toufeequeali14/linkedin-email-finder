# linkedin-email-finder

Playwright-based tool that mints reCAPTCHA v3 tokens on demand and resolves LinkedIn profile URLs to company and email via Anymail Finder.

## How it works

- `token_generator.py` opens a persistent Chromium profile on Anymail Finder and mints a fresh single-use reCAPTCHA token per request. On first run it performs one real search to discover the site key and action, then caches them in `recaptcha_action.json`.
- `email_finder.py` reads LinkedIn URLs from a text file, requests a token for each, posts the search from inside the browser page, and writes `account`, `company` and `email` to `emails.json`.

## Requirements

- Python 3.9+
- Playwright (Chromium)

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

`requirements.txt` contains one line: `playwright`

## Usage

1. Add LinkedIn profile URLs to `linkedin_urls.txt`, one per line:

```
   https://www.linkedin.com/in/some-profile/
```

2. Run:

```bash
   python email_finder.py
```