/* 使用頁前端邏輯：額度展示（/api/me）＋文轉劇操作流程（/convert）＋結果複製/下載
   —— 登入用戶專用；未登入跳轉 /login?next=/usage。 */
(function () {
  "use strict";
  if (!window.T2SAuth) return;
  if (!T2SAuth.requireAuth()) return;
  T2SAuth.bindLogout();

  /* ---------- DOM ---------- */
  var fileTab = document.querySelector('[data-tab="file"]');
  var textTab = document.querySelector('[data-tab="text"]');
  var filePanel = document.querySelector('[data-panel="file"]');
  var textPanel = document.querySelector('[data-panel="text"]');
  var fileInput = document.getElementById("file-input");
  var dropzone = document.getElementById("dropzone");
  var fileNameEl = document.getElementById("file-name");
  var storyText = document.getElementById("story-text");
  var charCount = document.getElementById("char-count");
  var convertBtn = document.getElementById("convert-btn");
  var btnLabel = convertBtn.querySelector(".btn-label");
  var btnLoading = convertBtn.querySelector(".btn-loading");
  var errorBox = document.getElementById("error-box");
  var resultCard = document.getElementById("result-card");
  var resultBody = document.getElementById("result-body");
  var metaEl = document.getElementById("meta");
  var copyBtn = document.getElementById("copy-btn");
  var downloadBtn = document.getElementById("download-btn");
  var quotaChip = document.getElementById("quota-chip");

  var currentContent = "";
  var selectedFile = null;

  /* ---------- 額度展示 ---------- */
  async function loadMe() {
    try {
      var resp = await T2SAuth.fetchAuth("/api/me");
      var data = await resp.json();
      if (resp.status === 401 || !data.ok) {
        T2SAuth.clearToken();
        T2SAuth.requireAuth();
        return;
      }
      renderQuota(data.usage);
    } catch (e) {
      quotaChip.textContent = "額度載入失敗";
    }
  }

  function renderQuota(u) {
    quotaChip.textContent = "本月剩餘 " + u.remaining + " / " + u.limit + " 次";
    var lowThreshold = Math.max(Math.ceil(u.limit * 0.2), 2);
    quotaChip.classList.toggle("low", u.remaining > 0 && u.remaining <= lowThreshold);
    quotaChip.classList.toggle("empty", u.remaining <= 0);
  }

  /* ---------- Tabs ---------- */
  function switchTab(name) {
    var isFile = name === "file";
    fileTab.classList.toggle("active", isFile);
    textTab.classList.toggle("active", !isFile);
    fileTab.setAttribute("aria-selected", String(isFile));
    textTab.setAttribute("aria-selected", String(!isFile));
    filePanel.hidden = !isFile;
    textPanel.hidden = isFile;
    hideError();
  }
  fileTab.addEventListener("click", function () { switchTab("file"); });
  textTab.addEventListener("click", function () { switchTab("text"); });

  /* ---------- File ---------- */
  fileInput.addEventListener("change", function () {
    selectedFile = fileInput.files[0] || null;
    fileNameEl.textContent = selectedFile ? selectedFile.name : "";
  });
  ["dragenter", "dragover"].forEach(function (ev) {
    dropzone.addEventListener(ev, function (e) {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach(function (ev) {
    dropzone.addEventListener(ev, function (e) {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });
  dropzone.addEventListener("drop", function (e) {
    var file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (!file) return;
    var ext = (file.name.split(".").pop() || "").toLowerCase();
    if (["txt", "md", "docx"].indexOf(ext) === -1) {
      showError("不支援的檔案類型：." + ext + "，請上傳 .txt / .md / .docx");
      return;
    }
    selectedFile = file;
    fileNameEl.textContent = file.name;
  });

  /* ---------- 字數統計 ---------- */
  storyText.addEventListener("input", function () {
    var n = storyText.value.length;
    charCount.textContent = n.toLocaleString();
    charCount.closest(".counter").classList.toggle("warn", n === 50000);
  });

  /* ---------- 轉換 ---------- */
  convertBtn.addEventListener("click", async function () {
    hideError();
    resultCard.hidden = true;

    var form = new FormData();
    if (fileTab.classList.contains("active")) {
      if (!selectedFile) {
        showError("請先選擇檔案，或切換到「貼上 / 打字」輸入文字");
        return;
      }
      form.append("file", selectedFile);
    } else {
      var text = storyText.value.trim();
      if (!text) {
        showError("請輸入或貼上至少一段故事文字");
        return;
      }
      form.append("text", text);
    }

    setLoading(true);
    try {
      var resp = await T2SAuth.fetchAuth("/convert", { method: "POST", body: form });
      var data = await resp.json();
      if (resp.status === 401 || data.error_code === "auth_required") {
        T2SAuth.clearToken();
        T2SAuth.requireAuth();
        return;
      }
      if (resp.status === 402 || data.error_code === "quota_exceeded") {
        var d = data.detail || {};
        var suffix = d.remaining != null ? "（剩餘 " + d.remaining + " 次）" : "";
        showError((data.error || "本月額度已用完") + suffix + "。可到落地頁查看方案。");
        return;
      }
      if (!resp.ok || !data.ok) {
        showError(data.error || "轉換失敗，請稍後重試");
        return;
      }
      currentContent = data.content;
      renderMeta(data);
      resultBody.textContent = data.content;
      resultCard.hidden = false;
      resultCard.scrollIntoView({ behavior: "smooth", block: "start" });
      loadMe(); // 轉換成功後刷新剩餘額度
    } catch (err) {
      showError("網路請求失敗：" + err.message);
    } finally {
      setLoading(false);
    }
  });

  function setLoading(on) {
    convertBtn.disabled = on;
    btnLabel.hidden = on;
    btnLoading.hidden = !on;
  }

  function renderMeta(data) {
    var chips = [];
    chips.push('<span class="chip">' + escapeHtml(data.input_type_label || "") + "</span>");
    chips.push(
      '<span class="chip dim">' +
        (data.language === "en" ? "英文輸出" : "中文輸出") +
        "</span>"
    );
    chips.push('<span class="chip dim">清洗後 ' + data.cleaned_length + " 字</span>");
    chips.push('<span class="chip dim">' + data.num_episodes + " 集</span>");
    chips.push(
      '<span class="chip">' +
        (data.break_by_shot ? "超過 800 字 · 按分鏡節點分段" : "800 字以內 · 緊湊連排") +
        "</span>"
    );
    if (data.sensitive_hits && data.sensitive_hits.length) {
      chips.push(
        '<span class="chip warn">⚠ 命中紅線：' +
          escapeHtml(data.sensitive_hits.join("、")) +
          "（請人工確認）</span>"
      );
    }
    if (data.problems && data.problems.length) {
      chips.push('<span class="chip danger">分鏡自檢：' + data.problems.length + " 條提示</span>");
    }
    metaEl.innerHTML = chips.join("");
  }

  /* ---------- 複製 ---------- */
  copyBtn.addEventListener("click", async function () {
    if (!currentContent) return;
    var text = exportText();
    try {
      await navigator.clipboard.writeText(text);
      flash(copyBtn, "已複製");
    } catch (err) {
      var ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
        flash(copyBtn, "已複製");
      } catch (_) {
        showError("複製失敗，請手動長按選擇複製");
      }
      document.body.removeChild(ta);
    }
  });

  /* ---------- 下載 .txt ---------- */
  downloadBtn.addEventListener("click", function () {
    if (!currentContent) return;
    var blob = new Blob([exportText()], { type: "text/plain;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = "分鏡稿.txt";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  });

  function exportText() {
    return currentContent + "\n\n本內容由 AI 生成，僅供參考";
  }

  /* ---------- 工具 ---------- */
  function flash(btn, text) {
    var orig = btn.textContent;
    btn.textContent = text;
    setTimeout(function () { btn.textContent = orig; }, 1200);
  }
  function showError(msg) {
    errorBox.textContent = msg;
    errorBox.hidden = false;
  }
  function hideError() {
    errorBox.hidden = true;
    errorBox.textContent = "";
  }
  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  loadMe();
})();