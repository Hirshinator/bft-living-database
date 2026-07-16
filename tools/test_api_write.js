// Mock enough of the runtime to actually RUN api/data.js's write path.
// jsc lacks URLSearchParams; Vercel's Node 18 runtime has it as a global.
// Shim it so the harness can exercise the real code path.
globalThis.URLSearchParams = function (init) {
  var m = {};
  if (init) Object.keys(init).forEach(function (k) { m[k] = init[k]; });
  this.set = function (k, v) { m[k] = v; };
  this.toString = function () {
    return Object.keys(m).map(function (k) {
      return encodeURIComponent(k) + "=" + encodeURIComponent(m[k]); }).join("&");
  };
};
var calls = [];
var airtableRows = {
  influencer: [
    { id: "rec1", fields: { name: "Alice", stance: "pro" } },
    { id: "rec2", fields: { name: "Bob",   stance: "neutral" } },
    { id: "rec3", fields: { name: "Carol", stance: "pro" } },
  ],
};
globalThis.fetch = function (url, opts) {
  opts = opts || {};
  var method = opts.method || "GET";
  calls.push(method + " " + url.replace("https://api.airtable.com/v0/", ""));
  if (url.indexOf("upstash") >= 0 || url.indexOf("redis") >= 0)
    return Promise.resolve({ ok: true, status: 200, json: function () { return Promise.resolve({ result: null }); } });
  if (method === "GET") {
    var t = decodeURIComponent(url.split("/")[5].split("?")[0]);
    return Promise.resolve({ ok: true, status: 200, json: function () {
      return Promise.resolve({ records: airtableRows[t] || [] }); } });
  }
  return Promise.resolve({ ok: true, status: 200, json: function () { return Promise.resolve({ records: [] }); } });
};
globalThis.setTimeout = function (fn) { fn(); return 0; };
var process = { env: { BFT_PASSCODE: "x", KV_REST_API_URL: "https://redis.test",
  KV_REST_API_TOKEN: "t", AIRTABLE_TOKEN: "pat_test", AIRTABLE_BASE_ID: "appTEST" } };
var module = { exports: null };
var fn = new Function("module", "process", "fetch", "setTimeout", "globalThis", "URLSearchParams", read("api/data.js"));
fn(module, process, globalThis.fetch, globalThis.setTimeout, globalThis, globalThis.URLSearchParams);
var handler = module.exports;

// Scenario: Bob's stance edited, Carol deleted, Dave added. Alice untouched.
var payload = { influencer: [
  { _id: "rec1", name: "Alice", stance: "pro" },
  { _id: "rec2", name: "Bob",   stance: "hostile" },
  {              name: "Dave",  stance: "pro" },
]};
var req = { method: "POST", headers: { "x-passcode": "x" }, body: { value: JSON.stringify(payload) } };
var out = null;
var res = { status: function (c) { this._c = c; return this; }, json: function (j) { out = { code: this._c, body: j }; } };

handler(req, res).then(function () {
  print("  response: " + JSON.stringify(out));
  var b = out.body;
  var ok = b && b.ok && b.updated === 1 && b.created === 1 && b.deleted === 1;
  print("  expected updated=1 (Bob), created=1 (Dave), deleted=1 (Carol)");
  print("  " + (ok ? "PASS -- diff writes only what changed" : "FAIL"));
  print("\n  airtable calls made:");
  calls.filter(function (c) { return c.indexOf("redis") < 0; }).forEach(function (c) { print("    " + c); });
}).catch(function (e) { print("  THREW: " + e); });
