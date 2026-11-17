"""Inspect raw page HTML and optionally request mobile PageSpeed Insights data."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import socket
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
MAX_HTML_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 5
HIDDEN_TAGS = {"head", "script", "style", "noscript", "template", "svg", "iframe", "canvas"}
BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt",
    "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr",
    "li", "main", "nav", "ol", "p", "section", "table", "tr", "ul",
}
PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?61[\s().-]?[2-478](?:[\s().-]?\d){8}|0[2-9](?:[\s().-]?\d){8})(?!\w)"
)
ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+(?:[A-Za-z0-9.'-]+\s+){0,5}"
    r"(?:street|st|road|rd|avenue|ave|drive|dr|parade|pde|boulevard|blvd|"
    r"crescent|cres|place|pl|terrace|tce|lane|ln|highway|hwy)\b",
    re.IGNORECASE,
)


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.h1: list[str] = []
        self.visible_parts: list[str] = []
        self.schema_types: set[str] = set()
        self.schema_errors = 0
        self._hidden_stack: list[str] = []
        self._title_depth = 0
        self._title_parts: list[str] = []
        self._h1_depth = 0
        self._h1_parts: list[str] = []
        self._script_is_jsonld = False
        self._script_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag in HIDDEN_TAGS:
            self._hidden_stack.append(tag)
        if tag == "title":
            self._title_depth += 1
            self._title_parts = []
        if tag == "h1":
            self._h1_depth += 1
            self._h1_parts = []
        if tag == "script":
            self._script_is_jsonld = (
                (attributes.get("type") or "").split(";", 1)[0].strip().lower()
                == "application/ld+json"
            )
            self._script_parts = []
        if tag == "meta" and (attributes.get("name") or "").strip().lower() == "description":
            self.description = (attributes.get("content") or "").strip()
        if tag in BLOCK_TAGS and not self._hidden_stack:
            self.visible_parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self._title_depth:
            self._title_depth -= 1
            if self._title_depth == 0:
                self.title = " ".join("".join(self._title_parts).split())
        if tag == "h1" and self._h1_depth:
            self._h1_depth -= 1
            if self._h1_depth == 0:
                heading = " ".join("".join(self._h1_parts).split())
                if heading:
                    self.h1.append(heading)
        if tag == "script" and self._script_is_jsonld:
            raw_schema = "".join(self._script_parts).strip()
            if raw_schema:
                try:
                    self._collect_schema_types(json.loads(raw_schema))
                except (json.JSONDecodeError, TypeError):
                    self.schema_errors += 1
            self._script_is_jsonld = False
            self._script_parts = []
        if tag in HIDDEN_TAGS:
            for index in range(len(self._hidden_stack) - 1, -1, -1):
                if self._hidden_stack[index] == tag:
                    del self._hidden_stack[index]
                    break
        if tag in BLOCK_TAGS and not self._hidden_stack:
            self.visible_parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self._title_depth:
            self._title_parts.append(data)
        if self._h1_depth:
            self._h1_parts.append(data)
        if self._script_is_jsonld:
            self._script_parts.append(data)
        if not self._hidden_stack:
            self.visible_parts.append(data)

    def _collect_schema_types(self, value: object) -> None:
        if isinstance(value, dict):
            schema_type = value.get("@type")
            if isinstance(schema_type, str):
                self.schema_types.add(schema_type)
            elif isinstance(schema_type, list):
                self.schema_types.update(item for item in schema_type if isinstance(item, str))
            for child in value.values():
                self._collect_schema_types(child)
        elif isinstance(value, list):
            for child in value:
                self._collect_schema_types(child)


def validate_public_url(url: str) -> None:
    """
        Check that the URL is public and safe to fetch
         accepts only HTTP or HTTPS URLs. It rejects localhost and hosts that resolve to private or non-public IP addresses.
    """
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only public http:// and https:// URLs are supported.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not allowed.")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
        raise ValueError("Localhost URLs are not allowed.")
    try:
        addresses = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            addresses = {
                ipaddress.ip_address(info[4][0])
                for info in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
            }
        except OSError as exc:
            raise ValueError(f"Could not resolve public host {host}: {exc}") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("The host must resolve only to public IP addresses.")


def fetch_page(url: str) -> tuple[bytes, str, int, str]:
    """
        downloads the page with timeouts, checks redirects one at a time, and validates each redirect destination too. It enforces the redirect and download-size limits. This helps avoid accidentally fetching local services or waiting forever on an unresponsive site.
    """
    current_url = url
    headers = {"User-Agent": "HarbourlineSEOScanner/1.0 (+local assignment tool)"}
    for redirect_number in range(MAX_REDIRECTS + 1):
        validate_public_url(current_url)
        try:
            response = requests.get(
                current_url,
                headers=headers,
                timeout=(8, 25),
                allow_redirects=False,
                stream=True,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Page fetch failed: {exc}") from exc

        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise RuntimeError("The site returned a redirect without a Location header.")
            if redirect_number >= MAX_REDIRECTS:
                raise RuntimeError(f"The page exceeded {MAX_REDIRECTS} redirects.")
            next_url = urljoin(current_url, location)
            if urlsplit(current_url).scheme == "https" and urlsplit(next_url).scheme != "https":
                raise RuntimeError("HTTPS-to-HTTP redirects are not followed.")
            current_url = next_url
            continue

        try:
            response.raise_for_status()
            chunks = []
            total = 0
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_HTML_BYTES:
                    raise RuntimeError(f"HTML response exceeds {MAX_HTML_BYTES} bytes.")
                chunks.append(chunk)
            return (
                b"".join(chunks),
                response.url,
                response.status_code,
                response.headers.get("Content-Type", ""),
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Page fetch failed: {exc}") from exc
        finally:
            response.close()
    raise RuntimeError("The page exceeded the redirect limit.")


def decode_html(content: bytes, content_type: str = "") -> str:
    """
        The response bytes are converted into text by decode_html. It uses the character encoding from the response when available, otherwise UTF-8
    """
    charset_match = re.search(r"charset\s*=\s*['\"]?([\w.-]+)", content_type, re.IGNORECASE)
    encoding = charset_match.group(1) if charset_match else "utf-8"
    try:
        return content.decode(encoding, errors="replace")
    except LookupError:
        return content.decode("utf-8", errors="replace")


def extract_page(html: str, url: str, final_url: str, status_code: int, source: str) -> dict:
    parser = PageParser()
    parser.feed(html)
    parser.close()
    visible_text = " ".join(" ".join(parser.visible_parts).split())
    """
         feeds that text into the parser and builds a result containing the URL, final URL after redirects, HTTP status, title, description, H1s, schema types, address/phone checks, and visible word count.
    """

    return {
        "url": url,
        "final_url": final_url,
        "source": source,
        "http_status": status_code,
        "title": parser.title,
        "meta_description": parser.description,
        "h1": parser.h1,
        "schema_types": sorted(parser.schema_types),
        "schema_parse_errors": parser.schema_errors,
        "phone_number_found": bool(PHONE_RE.search(html)),
        "street_address_found": bool(ADDRESS_RE.search(html)),
        "visible_word_count": len(re.findall(r"\b[\w'-]+\b", visible_text)),
    }


def fetch_pagespeed(url: str, retries: int = 3) -> dict:
    """
        separately calls Google’s PageSpeed Insights API using the mobile strategy. It looks for the performance score and Largest Contentful Paint (LCP).

        It retries temporary errors such as rate limiting, with a short increasing wait between attempts. If the service still fails, the result says unavailable and includes the reason. That means the content scan can still succeed even if PageSpeed does not.
    """
    params = {
        "url": url,
        "strategy": "mobile",
        "category": "performance",
    }
    api_key = os.environ.get("PAGESPEED_API_KEY")
    if api_key:
        params["key"] = api_key
    endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    last_error = "PageSpeed Insights did not return a result."

    for attempt in range(retries):
        try:
            response = requests.get(endpoint, params=params, timeout=(8, 35))
            if response.status_code == 429 or response.status_code >= 500:
                last_error = f"PageSpeed Insights returned HTTP {response.status_code}."
                response.close()
                if attempt + 1 < retries:
                    time.sleep(2**attempt)
                    continue
                break
            if response.status_code >= 400:
                last_error = f"PageSpeed Insights returned HTTP {response.status_code}."
                response.close()
                break
            try:
                data = response.json()
            finally:
                response.close()
            lighthouse = data.get("lighthouseResult", {})
            score = (
                lighthouse.get("categories", {}).get("performance", {}).get("score")
            )
            lcp = lighthouse.get("audits", {}).get("largest-contentful-paint", {}).get("numericValue")
            if score is None and lcp is None:
                last_error = data.get("error", {}).get("message", "The response contained no mobile performance metrics.")
                if attempt + 1 < retries:
                    time.sleep(2**attempt)
                    continue
                break
            return {
                "status": "available",
                "mobile_performance_score": round(score * 100) if isinstance(score, (int, float)) else None,
                "largest_contentful_paint_ms": round(lcp) if isinstance(lcp, (int, float)) else None,
                "error": None,
            }
        except (requests.RequestException, ValueError) as exc:
            last_error = str(exc)
            if attempt + 1 < retries:
                time.sleep(2**attempt)

    return {
        "status": "unavailable",
        "mobile_performance_score": None,
        "largest_contentful_paint_ms": None,
        "error": last_error,
    }


def result_filename(url: str) -> str:
    if url.startswith("local-html:"):
        name = url.split(":", 1)[1]
    else:
        parsed = urlsplit(url)
        name = parsed.hostname or "scan"
        if parsed.path.strip("/"):
            name += "-" + parsed.path.strip("/").replace("/", "-")
    slug = re.sub(r"[^a-zA-Z0-9-]+", "-", name).strip("-").lower()
    return (slug[:100] or "scan") + ".json"


def save_result(result: dict, output_dir: Path) -> Path:
    """
        writes the results as formatted JSON under scanner\results\. The output filename is made from the URL or fixture name
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / result_filename(result["url"])
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output_path


def scan_url(url: str) -> dict:
    """
        connects the public-page steps: validate, fetch, decode, extract, then request PageSpeed data.
    """
    validate_public_url(url)
    content, final_url, status, content_type = fetch_page(url)
    html = decode_html(content, content_type)
    result = extract_page(html, url, final_url, status, "remote")
    result["pagespeed"] = fetch_pagespeed(final_url)
    return result


def scan_local_html(path: Path) -> dict:
    """
         reads the file and runs the same content extraction. PageSpeed is marked unavailable because Google can’t measure a local file that isn’t publicly reachable.
    """
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError(f"HTML fixture is not a file: {resolved}")
    html = resolved.read_text(encoding="utf-8", errors="replace")
    label = "local-html:" + resolved.stem
    result = extract_page(html, label, label, 0, "local_html_fixture")
    result["pagespeed"] = {
        "status": "unavailable",
        "mobile_performance_score": None,
        "largest_contentful_paint_ms": None,
        "error": "PageSpeed Insights requires a publicly reachable URL.",
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("url", nargs="?", help="public page URL to scan")
    source.add_argument("--html", type=Path, help="scan a saved raw HTML fixture")
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()

    try:
        result = scan_local_html(args.html) if args.html else scan_url(args.url)
        output = save_result(result, args.output_dir)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Scan failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\nSaved: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
