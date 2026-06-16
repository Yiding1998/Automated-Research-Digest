# Research Digest

Research Digest is a small local automation tool that watches scholarly and web sources, deduplicates new items, summarizes them, and delivers a Markdown digest by file, email, or webhook.

It currently supports:

- arXiv
- Crossref
- Semantic Scholar
- PubMed
- Google News RSS
- Conference Alerts
- WikiCFP, optional and best-effort
- Manually watched conference/program pages
- Any RSS or Atom feed

## Quick Start

```powershell
cd C:\AI\codex\plug_skill
copy config.example.toml config.toml
python -m research_digest run --config config.toml --dry-run --ignore-state
```

This writes both:

- `output/latest_digest.md`
- `output/latest_digest.zh.md`

Edit `config.toml`:

- Put your field in `[profile].keywords`.
- Enable PubMed if you work in biomedicine.
- Add journal, lab, conference, or blog RSS URLs under `[[sources.rss.feeds]]`.
- Enable Semantic Scholar only if you have an API key, because anonymous calls can be rate limited.
- Turn on email delivery after setting SMTP environment variables.

## Email Setup

Set these environment variables before running:

```powershell
$env:SMTP_HOST="smtp.example.com"
$env:SMTP_PORT="587"
$env:SMTP_USERNAME="you@example.com"
$env:SMTP_PASSWORD="app-password"
$env:SMTP_FROM="you@example.com"
$env:SMTP_TO="you@example.com"
```

Then set:

```toml
[delivery.email]
enabled = true
to = ["you@example.com"]
```

Test email delivery:

```powershell
python -m research_digest send-test --config config.toml
```

## Optional LLM Summary

The default local summarizer is dependency-free and does not require an API key. To use an OpenAI-compatible chat-completions endpoint, set:

```powershell
$env:OPENAI_API_KEY="..."
```

Then set:

```toml
[summarization]
mode = "openai"
```

If the API call fails, Research Digest falls back to the local summarizer.

For DeepSeek, use:

```toml
[summarization]
mode = "openai"

[summarization.openai]
api_key_env = "DEEPSEEK_API_KEY"
base_url = "https://api.deepseek.com/chat/completions"
model = "deepseek-v4-flash"
timeout_seconds = 60
max_completion_tokens = 1400
```

Then set `DEEPSEEK_API_KEY` in your environment.

For Xiaomi MiMo Token Plan, use:

```toml
[summarization]
mode = "openai"

[summarization.openai]
api_key_env = "MIMO_API_KEY"
base_url = "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"
model = "mimo-v2.5-pro"
timeout_seconds = 120
max_completion_tokens = 1400
disable_thinking = true
```

## RSS Feeds

Turn on RSS in `config.toml`:

```toml
[sources.rss]
enabled = true

[[sources.rss.feeds]]
name = "Example Journal"
url = "https://example.com/rss"
kind = "paper"
max_results = 8
```

## Watched Conference Pages

For field-specific conferences that are not listed in generic aggregators, add official pages directly:

```toml
[sources.watched_pages]
enabled = true

[[sources.watched_pages.pages]]
title = "RPC 2026 - XVIII Conference on Resistive Plate Chambers and Related Detectors"
url = "https://rpc2026.uerj.br/"
kind = "conference"
source = "RPC 2026 Official Site"
venue = "Rio de Janeiro, Brazil"
date = "2026-09-14"
summary = "Official RPC 2026 page and program links."
```

Watched pages use a content hash, so they can be reported again when the page changes.

## Run For Real

```powershell
python -m research_digest run --config config.toml
```

The tool records delivered item fingerprints in `.research_digest_state.sqlite`, so routine runs only include new items.

By default, every run writes a main digest and a Chinese digest. Configure the paths here:

```toml
[delivery.file]
enabled = true
path = "output/latest_digest.md"
chinese_enabled = true
chinese_path = "output/latest_digest.zh.md"
```

If you pass `--output output/today.md`, the Chinese copy is written beside it as `output/today.zh.md`.

Useful flags:

```powershell
python -m research_digest run --config config.toml --since-days 3
python -m research_digest run --config config.toml --dry-run --ignore-state
python -m research_digest run --config config.toml --output output/today.md
```

## Windows Schedule

Install a daily Windows scheduled task:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows_task.ps1 -ConfigPath C:\AI\codex\plug_skill\config.toml -At 08:30
```

The task runs:

```powershell
python -m research_digest run --config <ConfigPath>
```

Use Task Scheduler to edit, pause, or remove it.
