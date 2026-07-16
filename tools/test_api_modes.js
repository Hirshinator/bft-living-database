globalThis.URLSearchParams = function (init) { var m = {}; if (init) Object.keys(init).forEach(function(k){m[k]=init[k];});
  this.set=function(k,v){m[k]=v;}; this.toString=function(){return Object.keys(m).map(function(k){return k+"="+m[k];}).join("&");}; };
globalThis.setTimeout = function (fn) { fn(); return 0; };

function makeFetch(store) {
  return function (url, opts) {
    opts = opts || {};
    if (url.indexOf("redis.test") >= 0) {
      if ((opts.method || "GET") === "GET" || url.indexOf("/get/") >= 0)
        return Promise.resolve({ ok: true, status: 200, json: function () {
          var k = decodeURIComponent(url.split("/get/")[1] || ""); return Promise.resolve({ result: store[k] || null }); } });
      var key = decodeURIComponent((url.split("/set/")[1] || "").split("?")[0]);
      store[key] = opts.body;
      return Promise.resolve({ ok: true, status: 200, json: function () { return Promise.resolve({ result: "OK" }); } });
    }
    return Promise.resolve({ ok: true, status: 200, json: function () {
      return Promise.resolve({ records: [{ id: "recA", fields: { name: "Alice", stance: "pro" } }] }); } });
  };
}
function load(env, fetchFn) {
  var module = { exports: null };
  var fn = new Function("module","process","fetch","setTimeout","globalThis","URLSearchParams", read("api/data.js"));
  fn(module, { env: env }, fetchFn, globalThis.setTimeout, globalThis, globalThis.URLSearchParams);
  return module.exports;
}
function call(h, req) {
  return new Promise(function (resolve) {
    var res = { status: function (c) { this._c = c; return this; }, json: function (j) { resolve({ code: this._c, body: j }); } };
    h(req, res);
  });
}
var BASE = { BFT_PASSCODE: "s3cret", KV_REST_API_URL: "https://redis.test", KV_REST_API_TOKEN: "t" };

(async function () {
  // --- BLOB MODE: no Airtable vars -> must behave exactly as before ---
  var store = { bft_database: '{"influencer":[{"name":"Legacy"}]}' };
  var h = load(BASE, makeFetch(store));
  var r = await call(h, { method: "GET", headers: { "x-passcode": "s3cret" } });
  print("BLOB GET      -> " + r.code + " mode=" + r.body.mode + " value=" + String(r.body.value).slice(0, 40));
  print("  " + (r.code === 200 && r.body.mode === "blob" ? "PASS -- existing app unaffected" : "FAIL"));

  r = await call(h, { method: "POST", headers: { "x-passcode": "s3cret" }, body: { value: '{"influencer":[{"name":"New"}]}' } });
  print("BLOB POST     -> " + r.code + " " + JSON.stringify(r.body));
  print("  " + (r.code === 200 && store.bft_database.indexOf("New") >= 0 ? "PASS -- blob still writes" : "FAIL"));

  // --- AUTH ---
  r = await call(h, { method: "GET", headers: { "x-passcode": "wrong" } });
  print("BAD PASSCODE  -> " + r.code + " " + JSON.stringify(r.body));
  print("  " + (r.code === 401 ? "PASS -- gate holds" : "FAIL"));

  // --- AIRTABLE MODE: GET + cache ---
  var env2 = Object.assign({}, BASE, { AIRTABLE_TOKEN: "pat", AIRTABLE_BASE_ID: "appX" });
  var store2 = {};
  var h2 = load(env2, makeFetch(store2));
  r = await call(h2, { method: "GET", headers: { "x-passcode": "s3cret" } });
  var v = JSON.parse(r.body.value);
  print("AIRTABLE GET  -> " + r.code + " mode=" + r.body.mode + " cached=" + r.body.cached
        + " influencers=" + v.influencer.length + " _id=" + v.influencer[0]._id);
  print("  " + (r.code === 200 && r.body.mode === "airtable" && v.influencer[0]._id === "recA"
        ? "PASS -- record IDs round-trip (the missing piece)" : "FAIL"));

  r = await call(h2, { method: "GET", headers: { "x-passcode": "s3cret" } });
  print("AIRTABLE GET2 -> cached=" + r.body.cached);
  print("  " + (r.body.cached === true ? "PASS -- cache hit, rate limit protected" : "FAIL"));
})();
