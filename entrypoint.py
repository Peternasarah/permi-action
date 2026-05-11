"""
Permi GitHub Action — entrypoint.py
Runs Permi scanner, formats results, posts PR comment, sets outputs.
"""

from __future__ import annotations

import json
import os
import sys
import subprocess
import urllib.request
import urllib.error
from pathlib import Path


# ── Read inputs from environment ──────────────────────────────────────────────
SCAN_PATH        = os.environ.get("PERMI_SCAN_PATH", ".")
SEVERITY         = os.environ.get("PERMI_SEVERITY", "high").lower()
FAIL_ON_FINDINGS = os.environ.get("PERMI_FAIL_ON_FINDINGS", "true").lower() == "true"
OUTPUT_FORMAT    = os.environ.get("PERMI_OUTPUT_FORMAT", "human").lower()
COMMENT_ON_PR    = os.environ.get("PERMI_COMMENT_ON_PR", "true").lower() == "true"
API_KEY          = os.environ.get("OPENROUTER_API_KEY", "").strip()
GITHUB_TOKEN     = os.environ.get("GITHUB_TOKEN", "").strip()

# GitHub context
GITHUB_EVENT_NAME = os.environ.get("GITHUB_EVENT_NAME", "")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")
GITHUB_SHA        = os.environ.get("GITHUB_SHA", "")
GITHUB_REF        = os.environ.get("GITHUB_REF", "")
GITHUB_OUTPUT     = os.environ.get("GITHUB_OUTPUT", "")
GITHUB_STEP_SUMMARY = os.environ.get("GITHUB_STEP_SUMMARY", "")
GITHUB_WORKSPACE  = os.environ.get("GITHUB_WORKSPACE", "/github/workspace")

# PR number for comments
PR_NUMBER = None
if GITHUB_EVENT_NAME == "pull_request":
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if event_path and Path(event_path).exists():
        try:
            with open(event_path) as f:
                event_data = json.load(f)
            PR_NUMBER = event_data.get("pull_request", {}).get("number")
        except Exception:
            pass


def log(msg: str, prefix: str = "[Permi Action]") -> None:
    print(f"{prefix} {msg}", flush=True)


def set_output(name: str, value: str) -> None:
    """Write a GitHub Actions output variable."""
    if GITHUB_OUTPUT:
        with open(GITHUB_OUTPUT, "a") as f:
            f.write(f"{name}={value}\n")
    else:
        print(f"::set-output name={name}::{value}")


def set_failed(message: str) -> None:
    print(f"::error::{message}", flush=True)
    sys.exit(1)


def write_step_summary(content: str) -> None:
    """Write to the GitHub Actions job summary."""
    if GITHUB_STEP_SUMMARY:
        try:
            with open(GITHUB_STEP_SUMMARY, "a") as f:
                f.write(content + "\n")
        except Exception:
            pass


def run_permi_scan() -> tuple[dict, str, int]:
    """
    Run permi scan and return (parsed_json, raw_output, exit_code).
    Always runs with --output json so we can parse results reliably.
    """
    scan_target = str(Path(GITHUB_WORKSPACE) / SCAN_PATH.lstrip("/").lstrip("./"))

    # Set up API key if provided
    if API_KEY:
        os.environ["OPENROUTER_API_KEY"] = API_KEY
        log("API key configured — AI false-positive filtering enabled.")
    else:
        log("No API key provided — running in offline mode (all raw findings shown).")
        log("Add OPENROUTER_API_KEY to your secrets for AI filtering.")

    cmd = [
        "permi", "scan",
        "--path", scan_target,
        "--output", "json",
        "--severity", SEVERITY,
    ]

    if not API_KEY:
        cmd.append("--offline")

    log(f"Running: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=GITHUB_WORKSPACE,
    )

    raw_output = result.stdout + result.stderr

    # Parse JSON output
    findings_data = {}
    try:
        # permi --output json prints a JSON array of findings
        findings_data = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        # If JSON parsing fails, findings_data stays empty
        findings_data = []

    return findings_data, raw_output, result.returncode


def severity_order(sev: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(sev.lower(), 0)


def filter_by_severity(findings: list, min_severity: str) -> list:
    """Return only findings at or above the minimum severity."""
    min_order = severity_order(min_severity)
    return [
        f for f in findings
        if severity_order(f.get("severity", "low")) >= min_order
    ]


def build_pr_comment(findings: list, scan_passed: bool, repo: str, sha: str) -> str:
    """Build a markdown comment for the PR."""
    sha_short = sha[:7] if sha else "unknown"

    if scan_passed:
        header = "## ✅ Permi Security Scan — Passed"
        summary = "No security vulnerabilities found at the configured severity threshold."
    else:
        high   = sum(1 for f in findings if f.get("severity") == "high")
        medium = sum(1 for f in findings if f.get("severity") == "medium")
        low    = sum(1 for f in findings if f.get("severity") == "low")
        header = f"## 🔴 Permi Security Scan — {len(findings)} Finding(s)"
        summary = f"**{high} High** · **{medium} Medium** · **{low} Low**"

    lines = [
        header,
        "",
        summary,
        "",
        f"*Scanned commit `{sha_short}` · Powered by [Permi](https://github.com/Peternasarah/permi)*",
        "",
    ]

    if findings:
        lines.append("### Findings")
        lines.append("")
        lines.append("| Severity | Rule | File | Line | Description |")
        lines.append("|----------|------|------|------|-------------|")

        for f in findings[:20]:  # cap at 20 rows to keep comment readable
            sev       = f.get("severity", "low").upper()
            rule_id   = f.get("rule_id", "")
            file_path = f.get("file", "")
            # Make path relative for readability
            if GITHUB_WORKSPACE and file_path.startswith(GITHUB_WORKSPACE):
                file_path = file_path[len(GITHUB_WORKSPACE):].lstrip("/")
            line_num  = f.get("line_number", "")
            desc      = f.get("description", "")[:80]
            sev_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🔵"}.get(sev, "⚪")
            lines.append(f"| {sev_emoji} {sev} | `{rule_id}` | `{file_path}` | {line_num} | {desc} |")

        if len(findings) > 20:
            lines.append("")
            lines.append(f"*...and {len(findings) - 20} more. See the full Action log for details.*")

        lines.append("")
        lines.append("### How to fix")
        lines.append("")
        lines.append(
            "Each finding includes a `Fix:` suggestion in the Action log. "
            "Run `permi scan --path .` locally to see inline fix templates."
        )

    lines.extend([
        "",
        "---",
        "*[Permi](https://github.com/Peternasarah/permi) — Built in Nigeria. For Nigeria. Then for the World.*",
    ])

    return "\n".join(lines)


def post_pr_comment(comment: str) -> None:
    """Post a comment on the pull request via GitHub API."""
    if not PR_NUMBER or not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        log("Skipping PR comment — not a pull request or missing token.")
        return

    api_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues/{PR_NUMBER}/comments"
    payload = json.dumps({"body": comment}).encode("utf-8")

    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={
            "Authorization": f"token {GITHUB_TOKEN}",
            "Content-Type":  "application/json",
            "Accept":        "application/vnd.github.v3+json",
            "User-Agent":    "Permi-GitHub-Action/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (200, 201):
                log("PR comment posted successfully.")
            else:
                log(f"PR comment returned status {resp.status}.")
    except urllib.error.HTTPError as e:
        log(f"Failed to post PR comment: HTTP {e.code} — {e.reason}")
    except Exception as e:
        log(f"Failed to post PR comment: {e}")


def build_step_summary(findings: list, scan_passed: bool) -> str:
    """Build the GitHub Actions job summary in markdown."""
    if scan_passed:
        return "## ✅ Permi Security Scan Passed\n\nNo vulnerabilities found.\n"

    high   = sum(1 for f in findings if f.get("severity") == "high")
    medium = sum(1 for f in findings if f.get("severity") == "medium")
    low    = sum(1 for f in findings if f.get("severity") == "low")

    lines = [
        "## 🔴 Permi Security Scan Failed",
        "",
        f"**{len(findings)} finding(s)** — {high} High · {medium} Medium · {low} Low",
        "",
        "| Severity | Rule | File | Line |",
        "|----------|------|------|------|",
    ]

    for f in findings[:15]:
        sev      = f.get("severity", "low").upper()
        rule_id  = f.get("rule_id", "")
        fp       = f.get("file", "")
        if GITHUB_WORKSPACE and fp.startswith(GITHUB_WORKSPACE):
            fp = fp[len(GITHUB_WORKSPACE):].lstrip("/")
        ln = f.get("line_number", "")
        emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🔵"}.get(sev, "⚪")
        lines.append(f"| {emoji} {sev} | `{rule_id}` | `{fp}` | {ln} |")

    lines.extend([
        "",
        "Run `permi scan --path .` locally to see full details and fix suggestions.",
        "",
        "*Powered by [Permi](https://github.com/Peternasarah/permi)*",
    ])

    return "\n".join(lines)


def main() -> None:
    log("Starting Permi Security Scanner")
    log(f"Repository : {GITHUB_REPOSITORY}")
    log(f"Event      : {GITHUB_EVENT_NAME}")
    log(f"Severity   : {SEVERITY}")
    log(f"Fail on    : {SEVERITY}+ findings = {FAIL_ON_FINDINGS}")

    # ── Run the scan ──────────────────────────────────────────────────────────
    findings_raw, raw_output, exit_code = run_permi_scan()

    # findings_raw is either a list (JSON array from permi) or empty
    all_findings = findings_raw if isinstance(findings_raw, list) else []

    # Filter to the configured severity threshold
    relevant = filter_by_severity(all_findings, SEVERITY)

    high_count   = sum(1 for f in all_findings if f.get("severity") == "high")
    medium_count = sum(1 for f in all_findings if f.get("severity") == "medium")
    low_count    = sum(1 for f in all_findings if f.get("severity") == "low")
    total_count  = len(all_findings)

    scan_passed = len(relevant) == 0

    # ── Print human-readable summary to Action log ────────────────────────────
    print("\n" + "═" * 60, flush=True)
    print("  PERMI SCAN SUMMARY", flush=True)
    print("═" * 60, flush=True)
    print(f"  Total findings : {total_count}", flush=True)
    print(f"  High           : {high_count}", flush=True)
    print(f"  Medium         : {medium_count}", flush=True)
    print(f"  Low            : {low_count}", flush=True)
    print(f"  Scan passed    : {'YES ✅' if scan_passed else 'NO ❌'}", flush=True)
    print("═" * 60 + "\n", flush=True)

    if not scan_passed:
        print("Findings requiring attention:", flush=True)
        for f in relevant:
            fp = f.get("file", "")
            if GITHUB_WORKSPACE and fp.startswith(GITHUB_WORKSPACE):
                fp = fp[len(GITHUB_WORKSPACE):].lstrip("/")
            print(
                f"  [{f.get('severity','').upper()}] {f.get('rule_id','')} — "
                f"{fp}:{f.get('line_number','')}",
                flush=True,
            )
            if f.get("ai_explanation"):
                print(f"    AI: {f['ai_explanation']}", flush=True)
        print("", flush=True)

    # ── Save report file ──────────────────────────────────────────────────────
    report_path = "/tmp/permi-report.md"
    try:
        report_content = build_pr_comment(all_findings, scan_passed, GITHUB_REPOSITORY, GITHUB_SHA)
        Path(report_path).write_text(report_content, encoding="utf-8")
        log(f"Report saved to {report_path}")
    except Exception as e:
        log(f"Could not save report: {e}")
        report_path = ""

    # ── Set GitHub Action outputs ─────────────────────────────────────────────
    set_output("findings_count", str(total_count))
    set_output("high_count",     str(high_count))
    set_output("medium_count",   str(medium_count))
    set_output("low_count",      str(low_count))
    set_output("scan_passed",    str(scan_passed).lower())
    set_output("report_path",    report_path)

    # ── Write job summary ─────────────────────────────────────────────────────
    write_step_summary(build_step_summary(all_findings, scan_passed))

    # ── Post PR comment ───────────────────────────────────────────────────────
    if COMMENT_ON_PR and GITHUB_EVENT_NAME == "pull_request":
        comment = build_pr_comment(all_findings, scan_passed, GITHUB_REPOSITORY, GITHUB_SHA)
        post_pr_comment(comment)

    # ── Exit with correct code ────────────────────────────────────────────────
    if not scan_passed and FAIL_ON_FINDINGS:
        log(f"Failing workflow — {len(relevant)} {SEVERITY}+ finding(s) found.")
        sys.exit(1)
    else:
        if not scan_passed:
            log(f"Found {len(relevant)} finding(s) but fail_on_findings=false — continuing.")
        else:
            log("Scan passed — no findings at configured severity threshold.")
        sys.exit(0)


if __name__ == "__main__":
    main()
