/* 落地頁前端邏輯：Email 訂閱收集與提交回饋 */
(function () {
  "use strict";

  var form = document.getElementById("subscribe-form");
  var emailInput = document.getElementById("subscribe-email");
  var msgEl = document.getElementById("subscribe-msg");
  if (!form || !emailInput || !msgEl) return;

  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  var busy = false;

  function showMsg(text, kind) {
    msgEl.textContent = text;
    msgEl.className = "subscribe-msg" + (kind ? " " + kind : "");
    msgEl.hidden = false;
  }

  function hideMsg() {
    msgEl.hidden = true;
    msgEl.textContent = "";
    msgEl.className = "subscribe-msg";
  }

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    if (busy) return;
    var email = emailInput.value.trim();
    if (!EMAIL_RE.test(email)) {
      showMsg("請輸入有效的 Email 地址", "err");
      return;
    }
    hideMsg();
    busy = true;
    var btn = form.querySelector(".subscribe-btn");
    var orig = btn.textContent;
    btn.disabled = true;
    btn.textContent = "送出中…";
    try {
      var payload = window.T2STracking
        ? T2STracking.attach({ email: email })
        : { email: email };
      var resp = await fetch("/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      var data = await resp.json();
      if (!resp.ok || !data.ok) {
        showMsg(data.error || "訂閱失敗，請稍後再試", "err");
        return;
      }
      showMsg("已收到！上線後會第一時間通知你。", "ok");
      form.reset();
    } catch (err) {
      showMsg("網路異常，請稍後再試", "err");
    } finally {
      busy = false;
      btn.disabled = false;
      btn.textContent = orig;
    }
  });
})();