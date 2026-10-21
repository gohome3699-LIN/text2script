/* 前端 i18n 验证：用 jsdom 真实执行 static/app.js，
   验证默认语言检测、三语切换、localStorage 记忆、输入输出内容不被翻译。
   用法：node scripts/verify_i18n.js（依赖 jsdom@21，见 web/README.md） */
"use strict";

const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");

const WEB_DIR = path.join(__dirname, "..");
const HTML = fs.readFileSync(path.join(WEB_DIR, "templates/index.html"), "utf-8")
  .replace(/{{ url_for\('static', filename='style\.css'\) }}/g, "/static/style.css")
  .replace(/{{ url_for\('static', filename='app\.js'\) }}/g, "/static/app.js");
const APP_JS = fs.readFileSync(path.join(WEB_DIR, "static/app.js"), "utf-8");

let passed = 0;
let failed = 0;
let failedNames = [];

function ok(name, cond, extra) {
  if (cond) {
    passed++;
    console.log("PASS  " + name + (extra ? "  (" + extra + ")" : ""));
  } else {
    failed++;
    failedNames.push(name);
    console.log("FAIL  " + name + (extra ? "  (" + extra + ")" : ""));
  }
}

function createDom(lang, savedLang) {
  const dom = new JSDOM(HTML, {
    runScripts: "outside-only",
    url: "http://localhost:5000/",
    pretendToBeVisual: true,
  });
  const { window } = dom;
  // 语言与存储控制
  Object.defineProperty(window.navigator, "language", {
    value: lang, configurable: true,
  });
  if (savedLang === null) {
    window.localStorage.removeItem("t2s-lang");
  } else {
    window.localStorage.setItem("t2s-lang", savedLang);
  }
  // fetch 桩：返回模拟转换结果
  window.fetch = async (url, opts) => {
    const body = new URLSearchParams(opts && opts.body).get("text") || "";
    return {
      ok: true,
      json: async () => ({
        ok: true,
        content: "剧本分镜稿\n镜1｜远景（3秒）\n台词：旁白：\"深夜雨巷，少年推开那扇门。\"",
        ai_notice: "本内容由 AI 生成，仅供参考",
        input_type: "summary",
        input_type_label: "故事梗概",
        cleaned_length: body.length,
        break_by_shot: body.length > 800,
        num_episodes: 1,
        warnings: [],
        problems: [],
        sensitive_hits: [],
      }),
    };
  };
  // jsdom 缺失的 DOM API 桩
  window.Element.prototype.scrollIntoView = function () {};
  window.HTMLElement.prototype.scrollIntoView = function () {};
  return dom;
}

function runIn(dom, fn) {
  return dom.window.eval("(" + fn.toString() + ")()");
}

/* ---------- 1. 默认语言检测 ---------- */
let dom = createDom("zh-CN", null);
dom.window.eval(APP_JS);
ok("默认 zh-CN：标题为简体", runIn(dom, () => document.querySelector("h1").textContent) === "纯文转剧本分镜",
   runIn(dom, () => document.querySelector("h1").textContent));
ok("默认 zh-CN：转换按钮为简体", runIn(dom, () => document.querySelector("#convert-btn .btn-label").textContent.trim()) === "转 换");
dom.window.close();

dom = createDom("en-US", null);
dom.window.eval(APP_JS);
ok("默认 en-US：标题为英文", runIn(dom, () => document.querySelector("h1").textContent) === "Text to Storyboard",
   runIn(dom, () => document.querySelector("h1").textContent));
dom.window.close();

dom = createDom("zh-TW", null);
dom.window.eval(APP_JS);
ok("默认 zh-TW：标题为繁体", runIn(dom, () => document.querySelector("h1").textContent) === "純文轉劇本分鏡",
   runIn(dom, () => document.querySelector("h1").textContent));
dom.window.close();

/* ---------- 2. 三语切换（点击语言按钮） ---------- */
dom = createDom("zh-CN", null);
dom.window.eval(APP_JS);

runIn(dom, () => document.querySelector('.lang-btn[data-lang="zh-TW"]').click());
ok("点「繁」：标题变繁体", runIn(dom, () => document.querySelector("h1").textContent) === "純文轉劇本分鏡",
   runIn(dom, () => document.querySelector("h1").textContent));
ok("点「繁」：转换按钮变'轉 換'", runIn(dom, () => document.querySelector("#convert-btn .btn-label").textContent.trim()) === "轉 換");
ok("点「繁」：复制按钮变'複製'", runIn(dom, () => document.querySelector("#copy-btn").textContent) === "複製");
ok("点「繁」：下载按钮变'下載 .txt'", runIn(dom, () => document.querySelector("#download-btn").textContent) === "下載 .txt");
ok("点「繁」：字符单位变'字'", runIn(dom, () => document.querySelector("[data-i18n=charSuffix]").textContent) === "字");
ok("点「繁」：文本域占位符为繁体", runIn(dom, () => document.querySelector("#story-text").getAttribute("placeholder")).indexOf("在這裡貼上") === 0);
ok("点「繁」：写入 localStorage", runIn(dom, () => localStorage.getItem("t2s-lang")) === "zh-TW");

runIn(dom, () => document.querySelector('.lang-btn[data-lang="en"]').click());
ok("点「EN」：标题变英文", runIn(dom, () => document.querySelector("h1").textContent) === "Text to Storyboard",
   runIn(dom, () => document.querySelector("h1").textContent));
ok("点「EN」：转换按钮变'Convert'", runIn(dom, () => document.querySelector("#convert-btn .btn-label").textContent.trim()) === "Convert");
ok("点「EN」：复制按钮变'Copy'", runIn(dom, () => document.querySelector("#copy-btn").textContent) === "Copy");
ok("点「EN」：下载按钮变'Download .txt'", runIn(dom, () => document.querySelector("#download-btn").textContent) === "Download .txt");
ok("点「EN」：字符单位变'chars'", runIn(dom, () => document.querySelector("[data-i18n=charSuffix]").textContent) === "chars");
ok("点「EN」：文本域占位符为英文", runIn(dom, () => document.querySelector("#story-text").getAttribute("placeholder")).indexOf("Paste or type") === 0);
ok("点「EN」：html lang 更新为 en", runIn(dom, () => document.documentElement.getAttribute("lang")) === "en");

runIn(dom, () => document.querySelector('.lang-btn[data-lang="zh-CN"]').click());
ok("点「简」：标题回简体", runIn(dom, () => document.querySelector("h1").textContent) === "纯文转剧本分镜",
   runIn(dom, () => document.querySelector("h1").textContent));

/* ---------- 3. 输入输出内容不被翻译 ---------- */
runIn(dom, () => {
  document.querySelector("#story-text").value = "深夜雨巷，少年推开那扇门，看见了三年前消失的父亲。";
  document.querySelector("#convert-btn").click();
});
setTimeout(() => {
  const bodyText = runIn(dom, () => document.querySelector("#result-body").textContent);
  const metaText = runIn(dom, () => document.querySelector("#meta").textContent);
  ok("转换结果展示中英混合：内容保持中文（不被翻译）", bodyText.indexOf("剧本分镜稿") === 0 && bodyText.indexOf("深夜雨巷") !== -1, bodyText.slice(0, 40));
  ok("输入类型 chip 按当前语言（简体）显示", metaText.indexOf("故事梗概") !== -1, metaText);
  ok("清洗字数 chip 按当前语言（简体）显示", metaText.indexOf("清洗后") !== -1, metaText);
  ok("结果卡片展示", runIn(dom, () => !document.querySelector("#result-card").hidden));
  ok("localStorage 记住 en? 当前应为 zh-CN", runIn(dom, () => localStorage.getItem("t2s-lang")) === "zh-CN");

  // 英文下再转换一次，chip 应为英文
  runIn(dom, () => document.querySelector('.lang-btn[data-lang="en"]').click());
  runIn(dom, () => document.querySelector("#convert-btn").click());
  setTimeout(() => {
    const metaTextEn = runIn(dom, () => document.querySelector("#meta").textContent);
    ok("英文界面：输入类型 chip 显示 'Synopsis'", metaTextEn.indexOf("Synopsis") !== -1, metaTextEn);
    ok("英文界面：清洗字数 chip 显示 'chars after cleaning'", metaTextEn.indexOf("chars after cleaning") !== -1, metaTextEn);
    const bodyEn = runIn(dom, () => document.querySelector("#result-body").textContent);
    ok("英文界面：输出内容仍为中文（不被翻译）", bodyEn.indexOf("剧本分镜稿") !== -1, bodyEn.slice(0, 40));

    /* ---------- 4. localStorage 记忆 ---------- */
    const savedLang = runIn(dom, () => localStorage.getItem("t2s-lang"));
    dom.window.close();
    const dom2 = createDom("zh-CN", savedLang);
    dom2.window.eval(APP_JS);
    ok("刷新后记住英文（localStorage 覆盖浏览器语言）", runIn(dom2, () => document.querySelector("h1").textContent) === "Text to Storyboard",
       runIn(dom2, () => document.querySelector("h1").textContent));
    dom2.window.close();

    /* ---------- 5. 错误提示按语言切换 ---------- */
    const dom3 = createDom("en-US", null);
    dom3.window.eval(APP_JS);
    runIn(dom3, () => document.querySelector("#convert-btn").click());
    setTimeout(() => {
      const errText = runIn(dom3, () => document.querySelector("#error-box").textContent);
      ok("英文界面空输入提示为英文", errText === "Please upload a file or enter text" || errText === "Please enter or paste at least one story", errText);
      dom3.window.close();

      console.log("\n==== 结果：" + passed + " 通过，" + failed + " 失败 ====");
      if (failed) {
        console.log("失败项：" + failedNames.join("、"));
        process.exit(1);
      }
      process.exit(0);
    }, 50);
  }, 80);
}, 80);