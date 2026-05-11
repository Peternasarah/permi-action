# Permi Security Scanner — GitHub Action

[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-Permi%20Security%20Scanner-blue?logo=github)](https://github.com/marketplace/actions/permi-security-scanner)
[![PyPI](https://img.shields.io/pypi/v/permi)](https://pypi.org/project/permi/)

AI-powered vulnerability scanner for your pull requests. Finds SQL injection, XSS, hardcoded secrets, USSD vulnerabilities, insecure functions, and more — then uses AI to filter out false positives so you only see findings that matter.

**Built in Nigeria. For Nigeria. Then for the World.**

---

## Quick Start

Add this to `.github/workflows/security.yml` in your repository:

```yaml
name: Security Scan

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  permi-scan:
    runs-on: ubuntu-latest
    name: Permi Security Scan

    permissions:
      contents: read
      pull-requests: write   # needed for PR comments

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Run Permi Security Scanner
        uses: Peternasarah/permi-action@v1
        with:
          severity: high
          openrouter_api_key: ${{ secrets.OPENROUTER_API_KEY }}
```

That is all. On every pull request, Permi will:
- Scan your code for vulnerabilities
- Use AI to remove false positives
- Post findings as a PR comment
- Block the merge if high severity issues are found

---

## What Permi Detects

| Category | Examples |
|----------|---------|
| **SQL Injection** | String concatenation, f-strings, % formatting in queries |
| **Cross-Site Scripting** | innerHTML assignment, document.write, Jinja2 \|safe |
| **Hardcoded Secrets** | Passwords, API keys, AWS keys, Paystack/Flutterwave secrets |
| **Insecure Practices** | eval(), exec(), pickle.loads(), SSL verification disabled, debug mode |
| **USSD Vulnerabilities** | Unvalidated sessionId, phoneNumber, serviceCode (Nigerian-specific) |

---

## Inputs

| Input | Description | Default |
|-------|-------------|---------|
| `path` | Directory to scan (relative to repo root) | `.` |
| `severity` | Minimum severity to fail on: `high`, `medium`, `low`, `all` | `high` |
| `fail_on_findings` | Fail the workflow if findings are found | `true` |
| `openrouter_api_key` | API key for AI false-positive filtering | `''` (offline mode) |
| `output_format` | Output format: `human`, `json`, `markdown` | `human` |
| `comment_on_pr` | Post findings as PR comment | `true` |
| `permi_version` | Permi version to install | `latest` |

---

## Outputs

| Output | Description |
|--------|-------------|
| `findings_count` | Total findings after AI filtering |
| `high_count` | High severity findings |
| `medium_count` | Medium severity findings |
| `low_count` | Low severity findings |
| `scan_passed` | `true` if no findings at threshold |
| `report_path` | Path to generated markdown report |

---

## Examples

### Report only — never block merges

```yaml
      - name: Run Permi Security Scanner
        uses: Peternasarah/permi-action@v1
        with:
          severity: high
          fail_on_findings: false
          openrouter_api_key: ${{ secrets.OPENROUTER_API_KEY }}
```

### Scan a specific directory only

```yaml
      - name: Run Permi Security Scanner
        uses: Peternasarah/permi-action@v1
        with:
          path: './src'
          severity: medium
          openrouter_api_key: ${{ secrets.OPENROUTER_API_KEY }}
```

### Use scan results in later steps

```yaml
      - name: Run Permi Security Scanner
        id: permi
        uses: Peternasarah/permi-action@v1
        with:
          openrouter_api_key: ${{ secrets.OPENROUTER_API_KEY }}

      - name: Check results
        run: |
          echo "Total findings: ${{ steps.permi.outputs.findings_count }}"
          echo "Scan passed: ${{ steps.permi.outputs.scan_passed }}"
```

### Without AI filtering (offline mode)

```yaml
      - name: Run Permi Security Scanner
        uses: Peternasarah/permi-action@v1
        with:
          severity: high
          # No openrouter_api_key — runs in offline mode
          # All raw findings are shown without AI filtering
```

---

## Setting Up the API Key

1. Go to [openrouter.ai](https://openrouter.ai) and create a free account
2. Generate an API key
3. In your GitHub repository, go to **Settings → Secrets and variables → Actions**
4. Click **New repository secret**
5. Name: `OPENROUTER_API_KEY`
6. Value: your OpenRouter API key

The AI filter removes false positives so you only see real vulnerabilities. Without it, Permi still works but shows all raw findings.

---

## PR Comment Example

When a pull request introduces a vulnerability, Permi posts a comment like this:

```
🔴 Permi Security Scan — 2 Finding(s)

2 High · 0 Medium · 0 Low

| Severity | Rule    | File           | Line | Description                          |
|----------|---------|----------------|------|--------------------------------------|
| 🔴 HIGH  | SQL001  | app/auth.py    | 8    | Raw string concatenation in SQL query |
| 🔴 HIGH  | SEC001  | app/config.py  | 12   | Hardcoded database password           |

Run `permi scan --path .` locally to see full details and fix suggestions.
```

---

## Nigerian-Specific Rules

Permi includes rules built specifically for the Nigerian development context:

- **USSD gateway vulnerabilities** — unvalidated sessionId, phoneNumber, serviceCode
- **Paystack and Flutterwave key exposure** — detects Nigerian payment gateway secrets
- **NDPR-relevant patterns** — helps with Nigeria Data Protection Act compliance

No foreign scanner understands this market the way Permi does.

---

## Installing Permi CLI

Use Permi locally during development:

```bash
pip install permi
permi scan --path ./myapp
permi scan --url https://yoursite.com
permi setup --api-key YOUR_OPENROUTER_KEY
```

---

## Links

- **CLI:** [pypi.org/project/permi](https://pypi.org/project/permi/)
- **Source:** [github.com/Peternasarah/permi](https://github.com/Peternasarah/permi)
- **Website:** [peternasarah.github.io/permi](https://peternasarah.github.io/permi)
- **Issues:** [github.com/Peternasarah/permi-action/issues](https://github.com/Peternasarah/permi-action/issues)

---

*Built by [Peter Nasarah Dashe](https://github.com/Peternasarah) — University of Jos, Nigeria*

*Built in Nigeria. For Nigeria. Then for the World.*
