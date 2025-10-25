#!/bin/bash
rm -rf ./build
rm -rf ./build
uv sync
uv run download_adb.py
uv run briefcase update --update-resources
uv run briefcase build && open ./build/adbfs