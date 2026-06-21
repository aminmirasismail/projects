# projects

This repo holds all of my personal projects. See below for setup and basic usage instructions.

## Structure

Each project lives in its own top-level folder with its own `pyproject.toml` and virtual environment. There's no shared root-level package — `cd` into a project and set it up independently.

## Prerequisite: install uv

uv manages the Python version and virtual environment for each project.

- Windows (winget): `winget install --id astral-sh.uv -e`
- Or follow the install instructions at https://docs.astral.sh/uv/getting-started/installation/

## Projects

- [dexter_handheld_mobile_agent](dexter_handheld_mobile_agent/README.md) — local push-to-talk mobile agent built into a piece of hardware.

See each project's own README for its setup and usage instructions.
