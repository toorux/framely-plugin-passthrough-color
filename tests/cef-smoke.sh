#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
: "${FRAMELY_CEF_ROOT:?Set FRAMELY_CEF_ROOT to the ARM64 CEF distribution}"
run_dir=$(mktemp -d)
trap 'kill "$server_pid" 2>/dev/null || true; rm -rf "$run_dir"' EXIT
server_pid=''
cp tests/fixture.html "$run_dir/index.html"
cp payload/page.js "$run_dir/page.js"
ln -s "$FRAMELY_CEF_ROOT/Release/icudtl.dat" "$run_dir/icudtl.dat"
c++ -std=c++17 -O2 -I"$FRAMELY_CEF_ROOT" tests/browser_probe.cpp -L"$FRAMELY_CEF_ROOT/Release" -lcef -Wl,-rpath,"$FRAMELY_CEF_ROOT/Release" -o "$run_dir/probe"
python3 - "$run_dir" <<'PYHTTP' &
import functools,http.server,pathlib,sys
root=pathlib.Path(sys.argv[1]);server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(root)))
(root/'port').write_text(str(server.server_port));server.serve_forever()
PYHTTP
server_pid=$!
for _ in {1..100}; do test -f "$run_dir/port" && break; sleep .05; done
FRAMELY_PREVIEW_DIR="$run_dir" "$run_dir/probe" "http://127.0.0.1:$(cat "$run_dir/port")/index.html" "$run_dir" --no-sandbox --disable-gpu --disable-gpu-compositing
