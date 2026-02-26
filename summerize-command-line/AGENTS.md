# Repository Guidelines

This repository contains a single Bash-based CLI for summarizing podcast and YouTube audio via `whisper-cli`, `yt-dlp`, and the `summarize` CLI.

## Project Structure & Module Organization
- `summarize-podcast` is the main executable script and holds all logic (URL detection, download, transcription, summarization).
- `README.md` documents installation, setup, and usage examples.
- `CLAUDE.md` captures operational best practices for Whisper and summarize configuration.
- `.claude/` stores local tooling state; avoid editing unless you know the workflow.

## Build, Test, and Development Commands
- `chmod +x summarize-podcast` marks the script as executable.
- `./summarize-podcast --help` prints supported flags and examples.
- `./summarize-podcast "https://feeds.simplecast.com/4YRRRgQN" 2` summarizes the latest two RSS episodes.
- `SUMMARIZE_WHISPER_CPP_MODEL_PATH=... ./summarize-podcast "https://youtube.com/watch?v=ID"` runs with an explicit model.

There is no build step; ensure dependencies are installed (`summarize`, `whisper-cli`, `yt-dlp`).

## Coding Style & Naming Conventions
- Use Bash with 4-space indentation and `set -e` semantics.
- Function names follow lower_snake_case (e.g., `get_rss_episodes`).
- Environment variables are uppercase (e.g., `SUMMARIZE_WHISPER_CPP_MODEL_PATH`).
- Quote variable expansions and URL arguments to avoid word-splitting.

## Testing Guidelines
- No automated tests are currently configured.
- Manually validate changes with one RSS feed and one YouTube URL, plus `--transcript` mode to verify the transcription path.

## Commit & Pull Request Guidelines
- Commit messages are short, imperative statements without prefixes (e.g., "Add RSS parsing guard").
- PRs should describe the change, include the commands run for verification, and link any sample URLs used.
- If behavior changes, update `README.md` examples accordingly.

## Configuration & Dependencies
- Whisper models are expected at `~/.local/share/whisper/` and can be overridden via `SUMMARIZE_WHISPER_CPP_MODEL_PATH`.
- Summarize CLI config lives at `~/.summarize/config.json`.
