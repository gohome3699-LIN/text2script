/* 纯文转剧本分镜 · 网页版前端逻辑（含中簡 / 繁体 / English 界面语言） */
(function () {
  "use strict";

  /* ================= i18n 字典 ================= */
  var I18N = {
    "zh-CN": {
      appTitle: "纯文转剧本分镜",
      appSub: "上传 .docx / .txt / .md，或直接粘贴 / 打字，一键生成纯文字档分镜稿",
      tabUpload: "上传文件",
      tabText: "粘贴 / 打字",
      dzMain: "点击选择文件，或拖拽到此处",
      dzSub: "支持 .docx / .txt / .md，最大 10MB",
      hint: "提示：上传后点到「转换」即可，文件内容不会被保存到服务器。",
      textPlaceholder:
        "在这里粘贴或输入你的故事：一句话创意、故事梗概、大纲、小说片段都可以。\n\n例如：外卖小哥获得读心术，在送餐途中一次次救下陌生人，却发现自己也被卷入更大的阴谋……",
      charSuffix: "字",
      convert: "转 换",
      converting: "转换中…",
      resultTitle: "分镜稿",
      copy: "复制",
      copied: "已复制",
      download: "下载 .txt",
      downloadName: "分镜稿.txt",
      aiNotice: "本内容由 AI 生成，仅供参考",
      footer: "纯文转剧本分镜 · 网页版",
      typeOneLine: "一句话创意",
      typeSummary: "故事梗概",
      typeExcerpt: "小说片段",
      typeOutline: "大纲/分卷",
      chipCleaned: "清洗后 {n} 字",
      chipEpisodes: "{n} 集",
      chipBreakByShot: "超过 800 字 · 按分镜节点分段",
      chipCompact: "800 字以内 · 紧凑连排",
      chipSensitive: "⚠ 命中红线：{list}（请人工确认）",
      chipProblems: "分镜自检：{n} 条提示",
      errNoInput: "请上传文件或输入文本",
      errEmptyText: "请输入或粘贴至少一段故事文本",
      errTooLong: "文本过长（{n} 字），请控制在 50000 字以内，或拆成多段转换",
      errBadExt: "不支持的文件类型：{ext}，请上传 .txt / .md / .docx",
      errSelectFile: "请先选择文件，或切换到「粘贴 / 打字」输入文本",
      errConvertFailed: "转换失败，请稍后重试",
      errNetwork: "网络请求失败：{msg}",
      errCopyFailed: "复制失败，请手动长按选择复制",
      errServer: "服务内部错误：{msg}",
      errMissingDocx: "服务器缺少 python-docx，无法读取 .docx 文件",
      errDocxBad: "无法解析该 .docx 文件，请确认文件未损坏或不是伪装的文档",
      errFileTooLarge: "上传文件过大（超过 10MB）",
    },
    "zh-TW": {
      appTitle: "純文轉劇本分鏡",
      appSub: "上傳 .docx / .txt / .md，或直接貼上 / 打字，一鍵生成純文字檔分鏡稿",
      tabUpload: "上傳檔案",
      tabText: "貼上 / 打字",
      dzMain: "點擊選擇檔案，或拖曳到此處",
      dzSub: "支援 .docx / .txt / .md，最大 10MB",
      hint: "提示：上傳後點到「轉換」即可，檔案內容不會被儲存到伺服器。",
      textPlaceholder:
        "在這裡貼上或輸入你的故事：一句話創意、故事梗概、大綱、小說片段都可以。\n\n例如：外賣小哥獲得讀心術，在送餐途中一次次救下陌生人，卻發現自己也被捲入更大的陰謀……",
      charSuffix: "字",
      convert: "轉 換",
      converting: "轉換中…",
      resultTitle: "分鏡稿",
      copy: "複製",
      copied: "已複製",
      download: "下載 .txt",
      downloadName: "分鏡稿.txt",
      aiNotice: "本內容由 AI 生成，僅供參考",
      footer: "純文轉劇本分鏡 · 網頁版",
      typeOneLine: "一句話創意",
      typeSummary: "故事梗概",
      typeExcerpt: "小說片段",
      typeOutline: "大綱/分卷",
      chipCleaned: "清洗後 {n} 字",
      chipEpisodes: "{n} 集",
      chipBreakByShot: "超過 800 字 · 按分鏡節點分段",
      chipCompact: "800 字以內 · 緊湊連排",
      chipSensitive: "⚠ 命中紅線：{list}（請人工確認）",
      chipProblems: "分鏡自檢：{n} 條提示",
      errNoInput: "請上傳檔案或輸入文字",
      errEmptyText: "請輸入或貼上至少一段故事文字",
      errTooLong: "文字過長（{n} 字），請控制在 50000 字以內，或拆成多段轉換",
      errBadExt: "不支援的檔案類型：{ext}，請上傳 .txt / .md / .docx",
      errSelectFile: "請先選擇檔案，或切換到「貼上 / 打字」輸入文字",
      errConvertFailed: "轉換失敗，請稍後重試",
      errNetwork: "網路請求失敗：{msg}",
      errCopyFailed: "複製失敗，請手動長按選擇複製",
      errServer: "服務內部錯誤：{msg}",
      errMissingDocx: "伺服器缺少 python-docx，無法讀取 .docx 檔案",
      errDocxBad: "無法解析該 .docx 檔案，請確認檔案未損壞或不是偽裝的文件",
      errFileTooLarge: "上傳檔案過大（超過 10MB）",
    },
    en: {
      appTitle: "Text to Storyboard",
      appSub:
        "Upload .docx / .txt / .md, or paste / type your story, and generate a plain-text storyboard in one click",
      tabUpload: "Upload",
      tabText: "Paste / Type",
      dzMain: "Click to select a file, or drag & drop here",
      dzSub: "Supports .docx / .txt / .md, up to 10MB",
      hint: 'Tip: click "Convert" after uploading. File contents are never stored on the server.',
      textPlaceholder:
        "Paste or type your story here: a one-line idea, synopsis, outline, or a novel excerpt all work.\n\nExample: A delivery rider gains telepathy and saves strangers on his routes, only to find himself dragged into a bigger conspiracy…",
      charSuffix: "chars",
      convert: "Convert",
      converting: "Converting…",
      resultTitle: "Storyboard",
      copy: "Copy",
      copied: "Copied",
      download: "Download .txt",
      downloadName: "storyboard.txt",
      aiNotice: "This content is AI-generated and for reference only",
      footer: "Text to Storyboard · Web App",
      typeOneLine: "One-line idea",
      typeSummary: "Synopsis",
      typeExcerpt: "Novel excerpt",
      typeOutline: "Outline / volumes",
      chipCleaned: "{n} chars after cleaning",
      chipEpisodes: "{n} episode(s)",
      chipBreakByShot: "Over 800 chars · split at storyboard nodes",
      chipCompact: "Within 800 chars · compact layout",
      chipSensitive: "⚠ Safety flag: {list} (please review manually)",
      chipProblems: "Storyboard check: {n} note(s)",
      errNoInput: "Please upload a file or enter text",
      errEmptyText: "Please enter or paste at least one story",
      errTooLong:
        "Text is too long ({n} chars). Please keep it under 50,000 chars or split it into parts",
      errBadExt: "Unsupported file type: {ext}. Please upload .txt / .md / .docx",
      errSelectFile:
        'Please choose a file first, or switch to "Paste / Type" to enter text',
      errConvertFailed: "Conversion failed. Please try again later",
      errNetwork: "Network request failed: {msg}",
      errCopyFailed: "Copy failed. Please select and copy the text manually",
      errServer: "Server error: {msg}",
      errMissingDocx: "The server is missing python-docx and cannot read .docx files",
      errDocxBad: "Cannot parse this .docx file. Please check it is not corrupted",
      errFileTooLarge: "Uploaded file is too large (over 10MB)",
    },
  };

  var LANGS = ["zh-CN", "zh-TW", "en"];
  var LANG_KEY = "t2s-lang";
  var INPUT_TYPE_KEYS = {
    one_line: "typeOneLine",
    summary: "typeSummary",
    excerpt: "typeExcerpt",
    outline: "typeOutline",
  };

  /* ================= DOM ================= */
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
  var langSwitch = document.getElementById("lang-switch");
  var docTitle = document.querySelector("title");

  var currentContent = "";
  var selectedFile = null;
  var lastData = null;
  var currentLang = "zh-CN";

  /* ================= i18n 工具 ================= */
  function t(key, vars) {
    var dict = I18N[currentLang] || I18N["zh-CN"];
    var s = dict[key] != null ? dict[key] : I18N["zh-CN"][key] != null ? I18N["zh-CN"][key] : key;
    if (vars) {
      s = s.replace(/\{(\w+)\}/g, function (_, k) {
        return vars[k] != null ? String(vars[k]) : "{" + k + "}";
      });
    }
    return s;
  }

  function detectLang() {
    var saved = null;
    try { saved = localStorage.getItem(LANG_KEY); } catch (e) { saved = null; }
    if (saved && LANGS.indexOf(saved) !== -1) return saved;
    var nav = (navigator.language || navigator.userLanguage || "zh-CN").toLowerCase();
    if (nav.indexOf("zh") === 0) {
      return /tw|hk|mo|hant/.test(nav) ? "zh-TW" : "zh-CN";
    }
    if (nav.indexOf("en") === 0) return "en";
    return "zh-CN";
  }

  function applyLang(lang) {
    currentLang = lang;
    document.documentElement.lang = lang;
    try { localStorage.setItem(LANG_KEY, lang); } catch (e) { /* 忽略 */ }
    docTitle.textContent = t("appTitle");
    // 语言按钮 active 态
    Array.prototype.forEach.call(langSwitch.querySelectorAll(".lang-btn"), function (b) {
      b.classList.toggle("active", b.getAttribute("data-lang") === lang);
    });
    // 静态文案
    Array.prototype.forEach.call(document.querySelectorAll("[data-i18n]"), function (el) {
      el.textContent = t(el.getAttribute("data-i18n"));
    });
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-i18n-placeholder]"),
      function (el) {
        el.setAttribute("placeholder", t(el.getAttribute("data-i18n-placeholder")));
      }
    );
    // 已有结果时按新语言重渲染 chips
    if (lastData) renderMeta(lastData);
    // 错误信息若仍在展示，切换为纯静态提示不保留具体错误文本
    hideError();
  }

  /* ================= Tabs ================= */
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

  /* ================= 初始化语言 ================= */
  LANGS.forEach(function (lang) {
    document
      .querySelector('.lang-btn[data-lang="' + lang + '"]')
      .addEventListener("click", function () {
        applyLang(lang);
      });
  });
  applyLang(detectLang());

  fileTab.addEventListener("click", function () { switchTab("file"); });
  textTab.addEventListener("click", function () { switchTab("text"); });

  /* ================= File ================= */
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
      showError(t("errBadExt", { ext: "." + ext }));
      return;
    }
    selectedFile = file;
    fileNameEl.textContent = file.name;
  });

  /* ================= 字数统计 ================= */
  storyText.addEventListener("input", function () {
    var n = storyText.value.length;
    charCount.textContent = n.toLocaleString();
    charCount.closest(".counter").classList.toggle("warn", n === 50000);
  });

  /* ================= 转换 ================= */
  convertBtn.addEventListener("click", async function () {
    hideError();
    resultCard.hidden = true;

    var form = new FormData();
    var ok = true;
    if (fileTab.classList.contains("active")) {
      if (!selectedFile) {
        showError(t("errSelectFile"));
        return;
      }
      form.append("file", selectedFile);
    } else {
      var text = storyText.value.trim();
      if (!text) {
        showError(t("errEmptyText"));
        return;
      }
      form.append("text", text);
    }
    if (!ok) return;

    setLoading(true);
    try {
      var resp = await fetch("/convert", { method: "POST", body: form });
      var data = await resp.json();
      if (!resp.ok || !data.ok) {
        showError(messageFromCode(data.error_code, data.error, data.detail));
        return;
      }
      lastData = data;
      currentContent = data.content;
      renderMeta(data);
      resultBody.textContent = data.content;
      resultCard.hidden = false;
      resultCard.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      showError(t("errNetwork", { msg: err.message }));
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
    var typeKey = data.input_type && INPUT_TYPE_KEYS[data.input_type];
    chips.push('<span class="chip">' + escapeHtml(typeKey ? t(typeKey) : data.input_type_label) + "</span>");
    chips.push('<span class="chip dim">' + escapeHtml(t("chipCleaned", { n: data.cleaned_length })) + "</span>");
    chips.push('<span class="chip dim">' + escapeHtml(t("chipEpisodes", { n: data.num_episodes })) + "</span>");
    chips.push(
      '<span class="chip">' +
        escapeHtml(data.break_by_shot ? t("chipBreakByShot") : t("chipCompact")) +
        "</span>"
    );
    if (data.sensitive_hits && data.sensitive_hits.length) {
      chips.push(
        '<span class="chip warn">' +
          escapeHtml(t("chipSensitive", { list: data.sensitive_hits.join("、") })) +
          "</span>"
      );
    }
    if (data.problems && data.problems.length) {
      chips.push(
        '<span class="chip danger">' +
          escapeHtml(t("chipProblems", { n: data.problems.length })) +
          "</span>"
      );
    }
    metaEl.innerHTML = chips.join("");
  }

  /* ================= 错误码映射 ================= */
  function messageFromCode(code, fallback, detail) {
    var vars = detail || {};
    switch (code) {
      case "no_input": return t("errNoInput");
      case "empty_text": return t("errEmptyText");
      case "too_long": return t("errTooLong", vars);
      case "bad_ext": return t("errBadExt", vars);
      case "missing_docx": return t("errMissingDocx");
      case "docx_bad": return t("errDocxBad");
      case "file_too_large": return t("errFileTooLarge");
      case "server_error": return t("errServer", { msg: detail && detail.msg ? detail.msg : "" });
      default: return fallback || t("errConvertFailed");
    }
  }

  /* ================= 复制 ================= */
  copyBtn.addEventListener("click", async function () {
    if (!currentContent) return;
    var text = exportText();
    try {
      await navigator.clipboard.writeText(text);
      flash(copyBtn, t("copied"));
    } catch (err) {
      // 旧浏览器 fallback：选中文本复制
      var ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
        flash(copyBtn, t("copied"));
      } catch (_) {
        showError(t("errCopyFailed"));
      }
      document.body.removeChild(ta);
    }
  });

  /* ================= 下载 .txt ================= */
  downloadBtn.addEventListener("click", function () {
    if (!currentContent) return;
    var blob = new Blob([exportText()], { type: "text/plain;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = t("downloadName");
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  });

  /* 复制/下载内容 = 分镜稿 + 当前语言的 AI 声明行 */
  function exportText() {
    return currentContent + "\n\n" + t("aiNotice");
  }

  /* ================= 工具 ================= */
  function flash(btn, text) {
    var key = btn === copyBtn ? "copy" : null;
    var orig = btn.textContent;
    btn.textContent = text;
    setTimeout(function () {
      btn.textContent = key ? t(key) : orig;
    }, 1200);
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
})();