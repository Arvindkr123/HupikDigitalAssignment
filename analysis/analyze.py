"""Clean the supplied Search Console export and write owner-friendly outputs."""

from __future__ import annotations

import csv
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "gsc_export.csv"
OPPORTUNITIES = ROOT / "opportunities.csv"
CONFLICTS = ROOT / "page_conflicts.csv"
SUMMARY = ROOT / "summary.md"
FIELDS = ("Query", "Page", "Clicks", "Impressions", "CTR", "Position")
BRAND_RE = re.compile(r"\bharbou?r\s*lines?\b", re.IGNORECASE)
SUBURB_RE = re.compile(r"\b(chatswood|parramatta)\b", re.IGNORECASE)
OTHER_LOCATION_RE = re.compile(
    r"\b(epping|westmead|sydney|north\s*sydney|ryde)\b", re.IGNORECASE
)
OUT_OF_AREA_RE = re.compile(r"\b(melbourne|brisbane|perth|adelaide|canberra)\b", re.IGNORECASE)
IRRELEVANT_INTENT_RE = re.compile(r"\b(jobs?|careers?|salary|course|training|degree)\b", re.IGNORECASE)

SERVICE_PAGES = {
    "womens-health": ("women's health", "womens health", "pregnancy", "pelvic"),
    "post-surgery-rehab": ("post surgery", "post-surgical", "rehab", "knee replacement"),
    "sports-injury": ("acl", "sport", "running", "ankle", "tennis elbow"),
    "back-neck-pain": ("back", "neck", "whiplash", "spine", "hip"),
    "dry-needling": ("dry needling", "massage"),
}
LOCAL_PAGES = {
    "chatswood": ("chatswood",),
    "parramatta": ("parramatta",),
}


def clean_query(value: str) -> str:
    """
        collapses extra whitespace in a query.
    """
    return " ".join((value or "").split())


def canonical_url(value: str) -> str:
    """
        makes URL variants comparable: it changes HTTP to HTTPS, removes www, trailing slashes, tracking parameters, and URL fragments.
    """
    value = (value or "").strip()
    if not value:
        return ""
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return value
    scheme = parsed.scheme.lower()
    if scheme == "http":
        scheme = "https"
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    port = parsed.port
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        host += f":{port}"
    path = parsed.path.rstrip("/") or "/"
    tracking_parameters = {"gclid", "fbclid", "dclid", "msclkid", "srsltid"}
    query = urlencode(
        [
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.casefold().startswith("utm_") and key.casefold() not in tracking_parameters
        ]
    )
    return urlunsplit((scheme, host, path, query, ""))


def url_variants(raw_url: str) -> tuple[bool, bool]:
    parsed = urlsplit((raw_url or "").strip())
    host = (parsed.hostname or "").lower()
    normalized_scheme = "https" if parsed.scheme.lower() == "http" else parsed.scheme.lower()
    noncanonical_host = host == "harbourlinephysio.example"
    noncanonical_scheme = parsed.scheme.lower() != normalized_scheme
    parameters = parse_qsl(parsed.query, keep_blank_values=True)
    has_tracking = any(
        key.casefold().startswith("utm_")
        or key.casefold() in {"gclid", "fbclid", "dclid", "msclkid", "srsltid"}
        for key, _ in parameters
    )
    return noncanonical_scheme or noncanonical_host, has_tracking


def number(value: str, *, blank: float | None = None) -> float | None:
    """
        parses values such as "1,200" into numbers; blank or invalid values become None
    """
    if value is None or not value.strip():
        return blank
    try:
        result = float(value.strip().replace(",", ""))
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def display_number(value: float | None, places: int = 2) -> str:
    """
        formats values neatly in output files
    """
    if value is None:
        return ""
    rounded = round(value, places)
    return str(int(rounded)) if rounded.is_integer() else f"{rounded:.{places}f}".rstrip("0").rstrip(".")


def is_branded(query: str) -> bool:
    """
        checks whether a query contains a clinic-name variation.
    """
    return bool(BRAND_RE.search(query))


def service_page_for(query: str) -> str | None:
    normalized = query.casefold()
    for slug, signals in SERVICE_PAGES.items():
        if any(signal in normalized for signal in signals):
            return f"/services/{slug}/"
    return None


def preferred_page(query: str, pages: list[dict]) -> tuple[dict, str]:
    """
        chooses a suggested page owner using location and service intent first, then booking/contact intent, and finally the page already ranking best.
    """
    normalized = query.casefold()
    nearby_location = {
        "epping": ("chatswood", "Epping is closer to the Chatswood location; confirm the clinic's catchment before targeting it."),
        "harris park": ("parramatta", "Harris Park is served most directly by the Parramatta location."),
        "westmead": ("parramatta", "Westmead is served most directly by the Parramatta location."),
    }
    for suburb in LOCAL_PAGES:
        if suburb in normalized:
            target = f"/{suburb}/"
            for page in pages:
                if urlsplit(page["page"]).path.rstrip("/") == target.rstrip("/"):
                    return page, f"The query names {suburb.title()}, so its location page is the clearest local destination."
            return {"page": f"https://www.harbourlinephysio.example{target}"}, (
                f"The query names {suburb.title()}; make that location page the owner even though it is not among the pages currently appearing."
            )
    for place, (suburb, explanation) in nearby_location.items():
        if place in normalized:
            target = f"/{suburb}/"
            for page in pages:
                if urlsplit(page["page"]).path.rstrip("/") == target.rstrip("/"):
                    return page, explanation
            return {"page": f"https://www.harbourlinephysio.example{target}"}, explanation

    service_path = service_page_for(query)
    if service_path:
        for page in pages:
            if urlsplit(page["page"]).path.rstrip("/") == service_path.rstrip("/"):
                return page, "The page is the closest match for the service named in the query."
        return {"page": f"https://www.harbourlinephysio.example{service_path}"}, (
            "The dedicated service page is the best owner, although it is not one of the pages currently appearing for this query."
        )

    if re.search(r"\b(cost|price|fees?|book|booking|appointment|contact|phone|call)\b", normalized):
        for page in pages:
            path = urlsplit(page["page"]).path
            if "contact" in path:
                return page, "The query asks about price or contact details, so the contact page is the best destination."
        for page in pages:
            if "book-online" in urlsplit(page["page"]).path:
                return page, "The query signals booking intent, so the booking page is the best destination."

    if re.search(r"\b(near me|physio|physiotherapy|clinic)\b", normalized):
        for page in pages:
            if urlsplit(page["page"]).path.rstrip("/") in ("", "/"):
                return page, "The query is broad rather than service-specific, so the home page should be the main entry point."

    best = min(pages, key=lambda page: (page["position"] is None, page["position"] or math.inf))
    return best, "No clear service or suburb signal identifies a better page; keep the page that currently ranks highest."


def load_and_clean(path: Path) -> tuple[list[dict], dict]:
    """
        reads the CSV and returns cleaned records plus counts of the problems it found
        Checks that the file has the expected columns.
        Reads each row and normalizes its query and page URL.
        Excludes the Grand total row from query analysis.
        Skips detail rows that have no query or page.
        Tracks blank clicks, CTR, or position, and zero positions.
        Removes exact duplicate rows so their metrics aren’t counted twice.
        Converts blank clicks to zero when possible, and drops invalid or negative metrics.
        Keeps clicks and impressions when position is missing, but marks that position unavailable for ranking.
        Recalculates CTR as clicks / impressions rather than trusting an inconsistent or blank source value.
        Groups rows with the same case-insensitive query and canonical page. It sums clicks and impressions and calculates an impression-weighted average position.
    """
    problems = Counter()
    exact_seen = set()
    records: list[dict] = []
    grand_total = None
    source_count = 0
    source_clicks = 0.0
    source_impressions = 0.0

    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError(f"Expected CSV columns {', '.join(FIELDS)}")

        for line_number, row in enumerate(reader, start=2):
            source_count += 1
            query = clean_query(row.get("Query", ""))
            raw_page = row.get("Page", "") or ""
            page = canonical_url(raw_page)

            if query.casefold() == "grand total":
                grand_total = {
                    "clicks": number(row.get("Clicks", "")),
                    "impressions": number(row.get("Impressions", "")),
                }
                problems["grand_total_rows_excluded"] += 1
                continue

            if not query or not page:
                problems["detail_rows_missing_query_or_page"] += 1
                continue

            raw_clicks = row.get("Clicks") or ""
            raw_ctr = row.get("CTR") or ""
            raw_position = row.get("Position") or ""
            if not raw_clicks.strip():
                problems["source_rows_with_blank_clicks"] += 1
            if not raw_ctr.strip():
                problems["source_rows_with_blank_ctr"] += 1
            if not raw_position.strip():
                problems["source_rows_with_blank_position"] += 1
            elif number(raw_position) == 0:
                problems["source_rows_with_zero_position"] += 1

            raw_key = tuple((row.get(field) or "").strip() for field in FIELDS)
            if raw_key in exact_seen:
                problems["exact_duplicate_rows_removed"] += 1
                duplicate_clicks = number(raw_clicks)
                duplicate_impressions = number(row.get("Impressions", ""))
                source_clicks += duplicate_clicks or 0.0
                source_impressions += duplicate_impressions or 0.0
                continue
            exact_seen.add(raw_key)
            url_variant, has_tracking = url_variants(raw_page)
            if url_variant:
                problems["page_scheme_or_host_variants_normalized"] += 1
            if has_tracking:
                problems["tracking_query_parameters_removed"] += 1

            clicks = number(raw_clicks)
            impressions = number(row.get("Impressions", ""))
            position = number(row.get("Position", ""))
            if clicks is None:
                if (row.get("Clicks") or "").strip():
                    problems["invalid_click_values"] += 1
                    continue
                clicks = 0.0
                problems["blank_clicks_assumed_zero"] += 1
            if impressions is None or impressions < 0:
                problems["invalid_or_missing_impressions"] += 1
                continue
            if clicks < 0:
                problems["negative_clicks_rows_dropped"] += 1
                continue
            source_clicks += clicks
            source_impressions += impressions

            if position is None:
                if (row.get("Position") or "").strip():
                    problems["invalid_position_values"] += 1
                else:
                    problems["blank_positions_excluded_from_rankings"] += 1
            elif position <= 0 or position > 100:
                problems["out_of_range_positions_excluded_from_rankings"] += 1
                position = None

            raw_ctr_value = number(raw_ctr)
            calculated_ctr = clicks / impressions if impressions else 0.0
            if raw_ctr_value is None or abs(raw_ctr_value - calculated_ctr) > 0.0001:
                problems["ctr_values_recomputed"] += 1

            records.append(
                {
                    "query": query,
                    "query_key": query.casefold(),
                    "page": page,
                    "clicks": clicks,
                    "impressions": impressions,
                    "position": position,
                }
            )

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in records:
        grouped[(record["query_key"], record["page"])].append(record)

    cleaned = []
    for (query_key, page), items in grouped.items():
        impressions = sum(item["impressions"] for item in items)
        clicks = sum(item["clicks"] for item in items)
        positioned = [item for item in items if item["position"] is not None]
        position_weight = sum(item["impressions"] for item in positioned)
        average_position = (
            sum(item["position"] * item["impressions"] for item in positioned) / position_weight
            if position_weight
            else None
        )
        if len(items) > 1:
            problems["query_page_groups_aggregated"] += 1
        cleaned.append(
            {
                "query": items[0]["query"],
                "query_key": query_key,
                "page": page,
                "clicks": clicks,
                "impressions": impressions,
                "ctr": clicks / impressions if impressions else 0.0,
                "position": average_position,
            }
        )

    return cleaned, {
        "problems": problems,
        "grand_total": grand_total,
        "source_count": source_count,
        "source_detail_clicks": source_clicks,
        "source_detail_impressions": source_impressions,
    }


def make_outputs(records: list[dict], metadata: dict) -> None:
    total_clicks = sum(row["clicks"] for row in records)
    total_impressions = sum(row["impressions"] for row in records)
    branded_clicks = sum(row["clicks"] for row in records if is_branded(row["query"]))
    branded_share = branded_clicks / total_clicks if total_clicks else 0.0

    opportunity_rows = []
    for row in records:
        position = row["position"]
        normalized = row["query"].casefold()
        if (
            is_branded(row["query"])
            or position is None
            or not (3 < position <= 20)
            or IRRELEVANT_INTENT_RE.search(normalized)
            or OUT_OF_AREA_RE.search(normalized)
        ):
            continue
        if row["impressions"] < 100:
            continue
        benchmark_ctr = 0.12 if position <= 10 else 0.05
        has_supported_intent = bool(service_page_for(normalized)) or bool(SUBURB_RE.search(normalized))
        has_other_location = bool(OTHER_LOCATION_RE.search(normalized)) and not bool(
            re.search(r"\b(chatswood|parramatta)\b", normalized)
        )
        informational = bool(re.search(r"\b(stretches?|how long|vs|heal)\b", normalized))
        relevance = 0.5 if informational else (1.2 if has_supported_intent else (0.8 if has_other_location else 1.0))
        score = max(0.0, row["impressions"] * (benchmark_ctr - row["ctr"])) * relevance
        if score <= 0:
            continue
        opportunity_rows.append(
            {
                "query": row["query"],
                "current_page": row["page"],
                "clicks": display_number(row["clicks"]),
                "impressions": display_number(row["impressions"]),
                "ctr": f"{row['ctr']:.4f}",
                "average_position": display_number(position),
                "benchmark_ctr": f"{benchmark_ctr:.2f}",
                "relevance_multiplier": f"{relevance:.1f}",
                "estimated_incremental_clicks": f"{score:.2f}",
                "priority_score": f"{score:.2f}",
            }
        )
    opportunity_rows.sort(key=lambda row: float(row["priority_score"]), reverse=True)

    opportunity_fields = [
        "query", "current_page", "clicks", "impressions", "ctr",
        "average_position", "benchmark_ctr", "relevance_multiplier",
        "estimated_incremental_clicks", "priority_score",
    ]
    with OPPORTUNITIES.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=opportunity_fields)
        writer.writeheader()
        writer.writerows(opportunity_rows)

    pages_by_query: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        pages_by_query[row["query_key"]].append(row)
    conflict_rows = []
    for rows in pages_by_query.values():
        unique_pages = {row["page"] for row in rows}
        if len(unique_pages) < 2:
            continue
        owner, reason = preferred_page(rows[0]["query"], rows)
        conflict_rows.append(
            {
                "query": rows[0]["query"],
                "competing_pages": " | ".join(sorted(unique_pages)),
                "recommended_owner": owner["page"],
                "reason": reason,
                "total_clicks": display_number(sum(row["clicks"] for row in rows)),
                "total_impressions": display_number(sum(row["impressions"] for row in rows)),
                "best_average_position": display_number(
                    min((row["position"] for row in rows if row["position"] is not None), default=None)
                ),
            }
        )
    conflict_rows.sort(key=lambda row: float(row["total_impressions"]), reverse=True)
    with CONFLICTS.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "query", "competing_pages", "recommended_owner", "reason",
                "total_clicks", "total_impressions", "best_average_position",
            ],
        )
        writer.writeheader()
        writer.writerows(conflict_rows)

    top = opportunity_rows[:3]
    top_queries = [row["query"] for row in top]
    local_focus = top_queries[-1] if top_queries else "local physio searches"
    broad_focus = ", ".join(f"`{query}`" for query in top_queries[:2]) or "high-impression non-branded searches"
    fixes = [
        f"Make the Chatswood and Parramatta pages stronger local destinations, starting with **{local_focus}**: put the location details, matching services, and call/book action near the top.",
        f"Improve the relevant landing pages for {broad_focus}; make the next step to call or book obvious and check that the page matches what the searcher wants.",
        "Review the overlapping-page list and choose one best page for each important query; update internal links so the same query is not split across competing pages.",
    ]
    summary = f"""# Search visibility: what to fix first

The export contains {len(records)} cleaned query-and-page combinations. About **{branded_share:.1%} of recorded clicks** came from searches containing Harbourline's name or a spelling variation. The remaining clicks came from searches that did not use the clinic's name; many were local or service-related.

I found **{len(opportunity_rows)} quick-win queries**: non-branded searches with at least 100 impressions and an average position from 4 through 20. The score is a rough estimate, not a promise: it compares current click-through rate with a simple position-based benchmark, then gives a modest boost to services and suburbs Harbourline actually serves. {len(conflict_rows)} queries appeared on more than one page; those should have one clear page to focus on.

## Three things to fix first

{chr(10).join(f"{i}. {line}" for i, line in enumerate(fixes, 1))}
"""
    SUMMARY.write_text(summary, encoding="utf-8")

    grand_total = metadata["grand_total"]
    print(f"Source records (including totals): {metadata['source_count']}")
    print(f"Cleaned query/page combinations: {len(records)}")
    print(f"Clicks: {display_number(total_clicks)}; impressions: {display_number(total_impressions)}")
    print(f"Branded clicks: {display_number(branded_clicks)} ({branded_share:.2%})")
    print(f"Quick wins: {len(opportunity_rows)}; competing queries: {len(conflict_rows)}")
    print("Cleaning findings:")
    for name, count in sorted(metadata["problems"].items()):
        if count:
            print(f"  {name}: {count}")
    if grand_total:
        print(
            "Source grand total: "
            f"{display_number(grand_total['clicks'])} clicks, "
            f"{display_number(grand_total['impressions'])} impressions"
        )
        print(
            "Source-row reconciliation difference: "
            f"{display_number(metadata['source_detail_clicks'] - (grand_total['clicks'] or 0))} clicks, "
            f"{display_number(metadata['source_detail_impressions'] - (grand_total['impressions'] or 0))} impressions"
        )
        print(
            "Difference vs cleaned detail rows (after removing exact duplicate rows): "
            f"{display_number(total_clicks - (grand_total['clicks'] or 0))} clicks, "
            f"{display_number(total_impressions - (grand_total['impressions'] or 0))} impressions"
        )
    print(f"Wrote {OPPORTUNITIES.name}, {CONFLICTS.name}, and {SUMMARY.name}.")


def main() -> int:
    path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else INPUT
    if not path.is_file():
        print(f"Input file not found: {path}", file=sys.stderr)
        return 2
    try:
        records, metadata = load_and_clean(path)
        make_outputs(records, metadata)
    except (OSError, ValueError, csv.Error) as exc:
        print(f"Analysis failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())