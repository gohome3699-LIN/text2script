/* M2 認證前端工具（body.member 各頁共用）：
   - access token 存 sessionStorage「t2s_access」（關閉分頁即失效）
   - fetchAuth：自動帶 Authorization: Bearer；401 時先 POST /api/auth/refresh
     續期一次並重試；續期失敗清除 token（呼叫方決定是否跳轉）
   - requireAuth：未登入跳轉 /login?next=<回跳路徑>
   - logout：呼叫後端撤銷 refresh cookie、清除 token、回登入頁
*/
(function () {
  "use strict";

  var TOKEN_KEY = "t2s_access";

  function getToken() {
    try { return sessionStorage.getItem(TOKEN_KEY); } catch (e) { return null; }
  }
  function setToken(t) {
    try { sessionStorage.setItem(TOKEN_KEY, t); } catch (e) { /* 忽略 */ }
  }
  function clearToken() {
    try { sessionStorage.removeItem(TOKEN_KEY); } catch (e) { /* 忽略 */ }
  }

  /* 用 refresh cookie 換新 access token；成功回傳 true */
  async function tryRefresh() {
    try {
      var resp = await fetch("/api/auth/refresh", { method: "POST" });
      var data = await resp.json();
      if (resp.ok && data.ok && data.access_token) {
        setToken(data.access_token);
        return true;
      }
    } catch (e) { /* 網路異常 */ }
    clearToken();
    return false;
  }

  /* fetch 包裝：帶 Bearer；401 時續期一次並重試 */
  async function fetchAuth(url, options) {
    options = options || {};
    options.headers = options.headers || {};
    var token = getToken();
    if (token) options.headers.Authorization = "Bearer " + token;
    var resp = await fetch(url, options);
    if (resp.status === 401) {
      var refreshed = await tryRefresh();
      if (refreshed) {
        options.headers.Authorization = "Bearer " + getToken();
        resp = await fetch(url, options);
      } else {
        clearToken();
      }
    }
    return resp;
  }

  /* 只允許站內路徑的回跳（防 open redirect） */
  function safeNext(next) {
    if (typeof next !== "string" || !next) return "/dashboard";
    if (next.charAt(0) !== "/" || next.charAt(1) === "/") return "/dashboard";
    return next;
  }

  /* 未登入跳轉登入頁；已登入回傳 true */
  function requireAuth() {
    if (getToken()) return true;
    var next = encodeURIComponent(location.pathname + (location.search || ""));
    location.href = "/login?next=" + next;
    return false;
  }

  /* 登出：撤銷 refresh + 清除 token + 回登入頁 */
  async function logout() {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } catch (e) { /* 忽略 */ }
    clearToken();
    location.href = "/login";
  }

  /* 綁定 .js-logout 按鈕 */
  function bindLogout() {
    var btn = document.querySelector(".js-logout");
    if (btn) {
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        logout();
      });
    }
  }

  window.T2SAuth = {
    getToken: getToken,
    setToken: setToken,
    clearToken: clearToken,
    tryRefresh: tryRefresh,
    fetchAuth: fetchAuth,
    safeNext: safeNext,
    requireAuth: requireAuth,
    logout: logout,
    bindLogout: bindLogout,
  };
})();