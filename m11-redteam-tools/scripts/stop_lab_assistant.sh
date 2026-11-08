#!/usr/bin/env bash
here="$(cd "$(dirname "$0")/../.." && pwd)"
pid_file="$here/toyscreen/logs/server.pid"
[ -f "$pid_file" ] && kill "$(cat "$pid_file")" 2>/dev/null && rm -f "$pid_file" && echo "ToyScreen stopped" || echo "not running"
