/* 儀表板前端邏輯：使用概況（/api/me）＋歷史記錄（/api/history） */
(function () {
  "use strict";
  if (!window.T2SAuth) return;
  if (!T2SAuth.requireAuth()) return;
  T2SAuth.bindLogout();

  var PLAN_NAMES = { free: "Free", pro: "Pro", studio: "Studio" };
  var INPUT_TYPE_NAMES = {
    one_line: "一句話創意",
    summary: "故事梗概",
    excerpt: "小說片段",
    outline: "大綱/分卷",
  };

  async function loadMe() {
    var resp = await T2SAuth.fetchAuth("/api/me");
    var data = await resp.json();
    if (resp.status === 401 || !data.ok) {
      T2SAuth.clearToken();
      T2SAuth.requireAuth();
      return;
    }
    renderMe(data.user, data.usage);
  }

  function renderMe(user, usage) {
    document.getElementById("me-email").textContent = user.email;
    document.getElementById("me-plan").textContent = PLAN_NAMES[user.plan] || user.plan;
    document.getElementById("me-used").textContent = usage.used + " / " + usage.limit + " 次";
    document.getElementById("me-remaining").textContent = usage.remaining + " 次";
    var pct = usage.limit > 0 ? Math.min(100, Math.round((usage.used / usage.limit) * 100)) : 0;
    var fill = document.getElementById("quota-fill");
    fill.style.width = pct + "%";
    var lowThreshold = Math.max(Math.ceil(usage.limit * 0.2), 2);
    fill.classList.toggle("low", usage.remaining > 0 && usage.remaining <= lowThreshold);
    fill.classList.toggle("empty", usage.remaining <= 0);
    var monthEl = document.getElementById("quota-month");
    if (monthEl) {
      monthEl.textContent = "計費週期：" + usage.month + "（每月 1 日重置）";
    }
  }

  async function loadHistory() {
    var resp = await T2SAuth.fetchAuth("/api/history");
    var data = await resp.json();
    if (resp.ok && data.ok) renderHistory(data.history || []);
  }

  function renderHistory(rows) {
    var list = document.getElementById("history-list");
    var empty = document.getElementById("history-empty");
    if (!rows.length) {
      empty.hidden = false;
      empty.textContent = "還沒有轉換紀錄，到「使用頁」開始第一次文轉劇吧。";
      return;
    }
    empty.hidden = true;
    list.innerHTML = rows.map(function (r) {
      var t = new Date(r.ts);
      var timeStr = isNaN(t.getTime())
        ? String(r.ts)
        : t.toLocaleString("zh-TW", { hour12: false });
      var typeLabel = INPUT_TYPE_NAMES[r.input_type] || r.input_type || "—";
      var chips =
        '<span class="chip">' + escapeHtml(typeLabel) + "</span>" +
        '<span class="chip dim">' + r.num_episodes + " 集</span>" +
        '<span class="chip dim">' + r.cleaned_length + " 字</span>";
      return (
        '<li class="history-item"><div class="history-main">' +
        '<div class="history-time">' + escapeHtml(timeStr) + "</div>" +
        '<div class="history-meta">' + chips + "</div></div></li>"
      );
    }).join("");
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  loadMe();
  loadHistory();
})();