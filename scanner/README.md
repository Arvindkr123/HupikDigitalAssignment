# Raw HTML scanner

## Run a public URL scan

From this directory, install the one dependency and scan a public page:

```powershell
python -m pip install -r requirements.txt
python scan.py https://www.sydneyphysio.com.au/
```

The scanner follows a small number of public redirects, refuses private/local hosts, limits page size, parses the returned HTML without JavaScript, and writes JSON under `results/`. PageSpeed Insights is retried up to three times. If that service fails or rate-limits the request, the SEO scan still completes and marks its performance fields unavailable. Set `PAGESPEED_API_KEY` only if you have one; it is optional.

To inspect the saved Part A HTML fixture, use `python scan.py --html ..\wordpress\chatswood-preview.html`. It is a fixture for the intended page content, not a claim that WordPress has been run locally.

## Human approval

Edit `approvals.csv` to mark each URL `yes` or `no`, then run:

```powershell
python draft.py
```

Only approved URLs with a saved scan result receive a draft in `outbox/`. The tool makes no LLM calls. Review every draft before sending it.
