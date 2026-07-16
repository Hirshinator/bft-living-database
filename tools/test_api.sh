#!/bin/sh
# Run the api/data.js tests with JavaScriptCore (ships with macOS).
# These EXERCISE the code against a mocked Airtable -- they do not merely parse it.
#   ./tools/test_api.sh
JSC=/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc
cd "$(dirname "$0")/.."
echo "=== syntax ==="
$JSC -e 'try{ new Function("module","process","fetch","setTimeout","globalThis","URLSearchParams", read("api/data.js")); print("SYNTAX OK"); }catch(e){ print("ERR: "+e); }'
echo "\n=== write path (diff logic) ==="; $JSC tools/test_api_write.js
echo "\n=== modes + auth + cache ==="; $JSC tools/test_api_modes.js
