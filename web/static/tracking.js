/* M1 T4 來源與轉換追蹤：捕捉 UTM / referrer / 頁面來源並供訂閱、註冊、登入歸因。
 *
 * 做法：
 * - 首次在 URL 中看到 utm_source 時，把 utm_* 參數、referrer、頁面路徑固化到
 *   localStorage（key: t2s_tracking）；站內跳轉因 URL 無 utm 不會覆蓋，避免稀釋歸因。
 * - attach(payload) 把已捕捉的來源附加到訂閱 / 註冊 / 登入請求 body。
 */
(function () {
  "use strict";

  var KEY = "t2s_tracking";
  var UTM_FIELDS = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"];

  function readParams() {
    var out = {};
    try {
      var q = (window.location.search || "").replace(/^\?/, "");
      if (!q) return out;
      q.split("&").forEach(function (pair) {
        var i = pair.indexOf("=");
        if (i < 0) return;
        var k = decodeURIComponent(pair.slice(0, i));
        var v = decodeURIComponent(pair.slice(i + 1));
        if (UTM_FIELDS.indexOf(k) >= 0 && v) out[k] = v.slice(0, 500);
      });
    } catch (e) { /* 忽略非法參數 */ }
    return out;
  }

  function readStored() {
    var cur = {};
    try { cur = JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (e) { /* ignore */ }
    return cur;
  }

  function writeStored(cur) {
    try { localStorage.setItem(KEY, JSON.stringify(cur)); } catch (e) { /* ignore */ }
  }

  /* 首次捕捉到 UTM 來源時固化；已有來源不覆蓋，避免站內跳轉稀釋歸因 */
  function capture() {
    var cur = readStored();
    if (cur.utm_source) return cur;
    var params = readParams();
    if (!params.utm_source) return cur;
    Object.keys(params).forEach(function (k) { cur[k] = params[k]; });
    cur.referrer = (document.referrer || "").slice(0, 500);
    cur.page = (window.location.pathname || "/").slice(0, 200);
    cur.captured_at = new Date().toISOString();
    writeStored(cur);
    return cur;
  }

  window.T2STracking = {
    capture: capture,
    get: readStored,
    attach: function (payload) {
      var cur = readStored();
      var keys = Object.keys(cur);
      if (!keys.length) return payload;
      keys.forEach(function (k) {
        if (typeof cur[k] === "string") payload[k] = cur[k];
      });
      return payload;
    },
  };

  T2STracking.capture();
})();