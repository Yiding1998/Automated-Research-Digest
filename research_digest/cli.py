from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .config import ConfigError, bool_setting, init_config, load_config
from .scoring import filter_and_score
from .sender import send_email, send_webhook, write_digest
from .sources import fetch_all
from .state import SeenState
from .summarizer import summarize


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(prog="research-digest")
    subcommands = parser.add_subparsers(dest="command", required=True)

    init_parser = subcommands.add_parser("init-config", help="copy config.example.toml to a target path")
    init_parser.add_argument("--path", default="config.toml")
    init_parser.add_argument("--overwrite", action="store_true")

    run_parser = subcommands.add_parser("run", help="fetch sources and create/send a digest")
    run_parser.add_argument("--config", default="config.toml")
    run_parser.add_argument("--since-days", type=int)
    run_parser.add_argument("--output")
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--ignore-state", action="store_true")
    run_parser.add_argument("--mark-seen", action="store_true", help="mark dry-run items as seen")

    test_parser = subcommands.add_parser("send-test", help="send a short SMTP test email")
    test_parser.add_argument("--config", default="config.toml")

    args = parser.parse_args(argv)
    try:
        if args.command == "init-config":
            path = init_config(args.path, overwrite=args.overwrite)
            print(f"Created {path}")
            return 0
        if args.command == "run":
            return _run(args)
        if args.command == "send-test":
            return _send_test(args)
    except ConfigError as exc:
        print(f"Config error: {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001 - CLI should fail cleanly
        print(f"Error: {exc}")
        return 1
    return 0


def _run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    run_settings = config.get("run", {})
    since_days = args.since_days or int(run_settings.get("lookback_days", 7))
    since = datetime.now(UTC) - timedelta(days=since_days)
    raw_items, errors = fetch_all(config, since=since)

    keywords = list(config["profile"]["keywords"])
    excludes = list(config["profile"].get("exclude_keywords", []))
    scored = filter_and_score(_dedupe(raw_items), keywords, excludes)
    max_total = int(run_settings.get("max_total_items", 40))
    scored = scored[:max_total]

    state_path = run_settings.get("state_path", ".research_digest_state.sqlite")
    state: SeenState | None = None
    try:
        if not args.ignore_state or not args.dry_run or args.mark_seen:
            state = SeenState(state_path)
        if not args.ignore_state:
            assert state is not None
            scored = [item for item in scored if not state.contains(item.fingerprint())]
        body = summarize(scored, config, errors)
        output_path = _resolve_output(args.output, config)
        if output_path:
            write_digest(output_path, body)
            print(f"Wrote digest: {Path(output_path).resolve()}")
        chinese_output_path = _resolve_chinese_output(args.output, config)
        chinese_body = ""
        if chinese_output_path:
            chinese_body = summarize(scored, config, errors, language="Chinese")
            write_digest(chinese_output_path, chinese_body)
            print(f"Wrote Chinese digest: {Path(chinese_output_path).resolve()}")
        if args.dry_run:
            print(body)
            if args.mark_seen and state is not None:
                state.mark_many([item.fingerprint() for item in scored])
            return 0

        subject = f"{config.get('profile', {}).get('name', 'Research Digest')} - {datetime.now().date().isoformat()}"
        if bool_setting(config, ("delivery", "email", "enabled")):
            send_email(config, subject, body)
            print("Sent email digest")
            if bool_setting(config, ("delivery", "email", "chinese_enabled")):
                if not chinese_body:
                    chinese_body = summarize(scored, config, errors, language="Chinese")
                send_email(config, f"{subject} (Chinese)", chinese_body)
                print("Sent Chinese email digest")
        if bool_setting(config, ("delivery", "webhook", "enabled")):
            send_webhook(config, body)
            print("Sent webhook digest")
        if state is not None:
            state.mark_many([item.fingerprint() for item in scored])
    finally:
        if state is not None:
            state.close()
    return 0


def _send_test(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    send_email(
        config,
        f"{config.get('profile', {}).get('name', 'Research Digest')} test",
        "Research Digest email delivery is working.\n",
    )
    print("Sent test email")
    return 0


def _dedupe(items: list[Any]) -> list[Any]:
    seen: set[str] = set()
    deduped = []
    for item in items:
        fingerprint = item.fingerprint()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped.append(item)
    return deduped


def _resolve_output(cli_output: str | None, config: dict[str, Any]) -> str | None:
    if cli_output:
        return cli_output
    file_settings = config.get("delivery", {}).get("file", {})
    if file_settings.get("enabled", False):
        return str(file_settings.get("path", "output/latest_digest.md"))
    return None


def _resolve_chinese_output(cli_output: str | None, config: dict[str, Any]) -> str | None:
    file_settings = config.get("delivery", {}).get("file", {})
    if not file_settings.get("enabled", False) or not file_settings.get("chinese_enabled", False):
        return None
    if cli_output:
        path = Path(cli_output)
        suffix = path.suffix or ".md"
        return str(path.with_name(f"{path.stem}.zh{suffix}"))
    return str(file_settings.get("chinese_path", "output/latest_digest.zh.md"))
