"""Create client email drafts only for scan URLs explicitly approved in CSV."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parent
APPROVALS = ROOT / "approvals.csv"
RESULTS = ROOT / "results"
OUTBOX = ROOT / "outbox"


def normalize_url(value: str) -> str:
    """
        makes minor URL formatting differences less likely to prevent a match. For example, it removes a trailing slash and normalizes the scheme and hostname to lowercase.
    """
    value = value.strip()
    if value.startswith("local-html:"):
        return value
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return value.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, ""))


def read_approvals(path: Path) -> dict[str, bool]:
    """
        checks that the CSV has exactly two columns: url and approved. Each approval must be yes or no; missing URLs, invalid values, and duplicate URLs cause an error rather than being silently accepted.
    """
    approvals: dict[str, bool] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["url", "approved"]:
            raise ValueError("approvals.csv must have exactly the columns: url, approved")
        for line_number, row in enumerate(reader, start=2):
            url = normalize_url(row.get("url") or "")
            approved = (row.get("approved") or "").strip().casefold()
            if not url:
                raise ValueError(f"Missing URL on approvals.csv line {line_number}.")
            if approved not in {"yes", "no"}:
                raise ValueError(f"Use yes or no in approvals.csv line {line_number}.")
            if url in approvals:
                raise ValueError(f"Duplicate approval URL on line {line_number}: {url}")
            approvals[url] = approved == "yes"
    return approvals


def draft_body(result: dict) -> str:
    """
         pulls the scan data into an email format. It includes the page title, meta description, H1 headings, structured-data types, visible word count, and PageSpeed result.
         It also calls out basic checks: whether the scanner found a phone number, street address, and H1. If PageSpeed was unavailable, it says so rather than making up a score. The email notes that these are automated observations and should be checked before anyone acts on them.
    """
    title = result.get("title") or "No page title was found"
    description = result.get("meta_description") or "No meta description was found"
    headings = result.get("h1") or []
    schema = ", ".join(result.get("schema_types") or []) or "No JSON-LD schema types were detected"
    pagespeed = result.get("pagespeed") or {}
    score = pagespeed.get("mobile_performance_score")
    lcp = pagespeed.get("largest_contentful_paint_ms")
    if score is None:
        performance = "The mobile performance check was unavailable."
    else:
        performance = f"The mobile performance score was {score}/100"
        if lcp is not None:
            performance += f", with LCP at {lcp} ms"
        performance += "."

    notes = []
    if not result.get("phone_number_found"):
        notes.append("We could not find a phone number in the page HTML.")
    if not result.get("street_address_found"):
        notes.append("We could not find a street address in the page HTML.")
    if not headings:
        notes.append("We did not find an H1 heading.")
    if not notes:
        notes.append("The page includes a phone number, a street address, and at least one H1 in its raw HTML.")

    return (
        "Subject: A few initial website visibility observations\n\n"
        "Hello,\n\n"
        f"We reviewed {result.get('final_url') or result['url']} and wanted to share a few initial observations:\n\n"
        f"- Page title: {title}\n"
        f"- Meta description: {description}\n"
        f"- H1 headings: {', '.join(headings) if headings else 'None found'}\n"
        f"- Structured data types: {schema}\n"
        f"- Visible page text: {result.get('visible_word_count', 0)} words\n"
        f"- {performance}\n"
        + "".join(f"- {note}\n" for note in notes)
        + "\nThese are automated observations, not a full SEO or clinical review. Please check the page details before acting on them.\n\n"
        "Best,\nHupik Digital"
    )


def draft_filename(url: str) -> str:
    """
        creates a consistent filename from the URL using a short hash. The draft is saved as a .txt file in scanner\outbox\
    """
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    return f"email-{digest}.txt"


def create_drafts(
    approvals_path: Path = APPROVALS,
    results_dir: Path = RESULTS,
    outbox_dir: Path = OUTBOX,
) -> list[Path]:
    """
        reads the saved JSON scan results and matches each one to the approval list. If a URL is approved but has no scan result, it stops and reports which result is missing. That prevents a blank or incomplete email from being generated.
    """
    approvals = read_approvals(approvals_path)
    results_by_url: dict[str, tuple[Path, dict]] = {}
    for result_path in sorted(results_dir.glob("*.json")):
        result = json.loads(result_path.read_text(encoding="utf-8"))
        url = normalize_url(result.get("url", ""))
        if url:
            results_by_url[url] = (result_path, result)

    missing = [url for url, approved in approvals.items() if approved and url not in results_by_url]
    if missing:
        raise FileNotFoundError("Approved URL has no scan result: " + ", ".join(missing))

    outbox_dir.mkdir(parents=True, exist_ok=True)
    manifest = outbox_dir / ".generated-by-draft.json"
    previous_files = []
    if manifest.exists():
        previous_files = json.loads(manifest.read_text(encoding="utf-8"))

    created = []
    current_files = []
    for url, approved in approvals.items():
        if not approved:
            continue
        result = results_by_url[url][1]
        filename = draft_filename(url)
        path = outbox_dir / filename
        path.write_text(draft_body(result) + "\n", encoding="utf-8")
        created.append(path)
        current_files.append(filename)

    for filename in previous_files:
        if filename not in current_files and Path(filename).name == filename and filename.startswith("email-") and filename.endswith(".txt"):
            stale_path = outbox_dir / filename
            if stale_path.is_file():
                stale_path.unlink()
    manifest.write_text(json.dumps(current_files, indent=2) + "\n", encoding="utf-8")
    return created


def main() -> int:
    try:
        created = create_drafts()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Draft creation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Created {len(created)} approved draft(s).")
    for path in created:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
