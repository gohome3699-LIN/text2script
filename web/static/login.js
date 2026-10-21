/* 登入頁前端邏輯：登入 / 註冊雙模式切換，成功後保存 access token 並跳轉 */
(function () {
  "use strict";
  if (!window.T2SAuth) return;

  var mode = "login";
  var form = document.getElementById("auth-form");
  var emailInput = document.getElementById("email");
  var passwordInput = document.getElementById("password");
  var password2Input = document.getElementById("password2");
  var confirmField = document.getElementById("confirm-field");
  var btn = document.getElementById("auth-btn");
  var msgEl = document.getElementById("auth-msg");
  var subEl = document.getElementById("auth-sub");
  var switchNote = document.getElementById("auth-switch-note");
  var switchBtn = document.getElementById("switch-mode");
  var tabLogin = document.getElementById("tab-login");
  var tabSignup = document.getElementById("tab-signup");

  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  var busy = false;

  function showMsg(text, kind) {
    msgEl.textContent = text;
    msgEl.className = "auth-msg" + (kind ? " " + kind : "");
    msgEl.hidden = false;
  }
  function hideMsg() {
    msgEl.hidden = true;
    msgEl.textContent = "";
    msgEl.className = "auth-msg";
  }

  function setMode(m) {
    mode = m;
    var isSignup = m === "signup";
    tabLogin.classList.toggle("active", !isSignup);
    tabSignup.classList.toggle("active", isSignup);
    tabLogin.setAttribute("aria-selected", String(!isSignup));
    tabSignup.setAttribute("aria-selected", String(isSignup));
    confirmField.hidden = !isSignup;
    password2Input.required = isSignup;
    btn.textContent = isSignup ? "註 冊" : "登 入";
    subEl.textContent = isSignup ? "建立帳號，馬上開始文轉劇" : "登入以繼續使用";
    switchBtn.textContent = isSignup ? "返回登入" : "立即註冊";
    switchNote.firstChild.nodeValue = isSignup ? "已經有帳號？" : "還沒有帳號？";
    hideMsg();
  }

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    if (busy) return;
    var email = emailInput.value.trim();
    var password = passwordInput.value;
    if (!EMAIL_RE.test(email)) {
      showMsg("請輸入有效的 Email 地址", "err");
      return;
    }
    if (password.length < 6) {
      showMsg("密碼長度需至少 6 個字元", "err");
      return;
    }
    if (mode === "signup" && password !== password2Input.value) {
      showMsg("兩次輸入的密碼不一致", "err");
      return;
    }
    hideMsg();
    busy = true;
    var orig = btn.textContent;
    btn.disabled = true;
    btn.textContent = "送出中…";
    var url = mode === "signup" ? "/api/auth/signup" : "/api/auth/login";
    try {
      var payload = window.T2STracking
        ? T2STracking.attach({ email: email, password: password })
        : { email: email, password: password };
      var resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      var data = await resp.json();
      if (!resp.ok || !data.ok) {
        showMsg(data.error || "請求失敗，請稍後再試", "err");
        return;
      }
      T2SAuth.setToken(data.access_token);
      var next = new URLSearchParams(location.search).get("next");
      location.href = T2SAuth.safeNext(next);
    } catch (err) {
      showMsg("網路異常，請稍後再試", "err");
    } finally {
      busy = false;
      btn.disabled = false;
      btn.textContent = orig;
    }
  });

  switchBtn.addEventListener("click", function () {
    setMode(mode === "login" ? "signup" : "login");
  });
  tabLogin.addEventListener("click", function () { setMode("login"); });
  tabSignup.addEventListener("click", function () { setMode("signup"); });
})();