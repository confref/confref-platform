/* Feedback on the data (kit 1, decision 0008): a panel that explains how feedback works, takes text the visitor
   selects on the page, and prepares an issue in the public tracker of confref-data on GitHub. The issue text can also
   be copied, to send it to the project or keep it. Nothing is sent anywhere by this script: it only builds a link and
   a text. Any element with data-cr-feedback opens the panel; elements with data-cr-iri name the resource their
   content is about. */
(function () {
  "use strict";
  if (window.crFeedback) return;
  window.crFeedback = true;

  var REPO = "https://github.com/confref/confref-data";
  var CONTACT = "https://www.confref.org/legal/";
  var GUIDE = "https://www.confref.org/feedback/";
  var CONFIDENT = "https://www.confident-conference.org/index.php/ANNOUNCE";
  var BASE = "https://id.confref.org/";
  var OURS = /^\/((series|event|data|datasets|ontology)\/.+?)(\.(html|ttl|jsonld|nt|rdf))?\/?$/;
  var MAX_QUOTE = 1500, MAX_URL = 7500;
  var KEY = "cr-feedback:" + location.pathname;

  // ---- what the page is about -------------------------------------------------------------------------------
  function toIri(s) {
    if (!s) return "";
    try { var m = new URL(String(s).trim(), location.href).pathname.match(OURS); } catch (e) { return ""; }
    return m ? BASE + m[1] : "";
  }
  function pageSubject() {
    var meta = document.querySelector('meta[name="cr:subject"]');
    if (meta && meta.content) return meta.content;
    var param = new URLSearchParams(location.search).get("iri");
    if (param) return toIri(param) || param;
    var canon = document.querySelector('link[rel="canonical"]');
    if (canon && toIri(canon.href)) return toIri(canon.href);
    return toIri(location.href);
  }

  // ---- the selection: kept while the panel is open ----------------------------------------------------------
  var panel = null, picked = { text: "", iri: "" };
  function insidePanel(node) { return panel && node && panel.contains(node.nodeType === 1 ? node : node.parentNode); }
  document.addEventListener("selectionchange", function () {
    if (!panel || panel.hidden) return;
    var sel = window.getSelection();
    if (!sel || sel.isCollapsed || insidePanel(sel.anchorNode)) return;
    var text = sel.toString().replace(/\s+\n/g, "\n").trim();
    if (!text) return;
    var el = sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement;
    var holder = el && el.closest ? el.closest("[data-cr-iri]") : null;
    picked = { text: text.slice(0, MAX_QUOTE), iri: holder ? holder.getAttribute("data-cr-iri") : "" };
    if (picked.iri) field("iri").value = picked.iri;
    field("quote").value = picked.text;
    update();
  });

  // ---- the panel ----------------------------------------------------------------------------------------------
  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    for (var k in attrs || {}) {
      if (k === "text") e.textContent = attrs[k]; else if (k === "html") e.innerHTML = attrs[k]; else e.setAttribute(k, attrs[k]);
    }
    (kids || []).forEach(function (c) { if (c) e.append(c); });
    return e;
  }
  function field(name) { return panel.querySelector('[name="cr-fb-' + name + '"]'); }
  function labelled(text, control, hint) {
    var id = "cr-fb-" + control.getAttribute("name").slice(6);
    control.id = id;
    return el("div", { class: "cr-fb-field" }, [el("label", { for: id, text: text }), control,
      hint ? el("p", { class: "cr-fb-hint", text: hint }) : null]);
  }
  function build() {
    panel = el("aside", { class: "cr-fb", role: "dialog", "aria-modal": "false", "aria-labelledby": "cr-fb-title", hidden: "" });
    var close = el("button", { type: "button", class: "cr-fb-close", "aria-label": "Close", text: "×" });
    close.addEventListener("click", hide);
    var ext = ' target="_blank" rel="noopener"';
    var intro = el("div", { class: "cr-fb-step", "data-step": "1" }, [
      el("p", { html: "Feedback on the data of confref goes to the public issue tracker of " +
        '<a href="' + REPO + '/issues"' + ext + ">confref-data</a> on GitHub, where it is answered and can be followed." }),
      el("p", { text: "Any feedback is welcome there, above all on how confref links the records of its sources and " +
        "groups them into series and events." }),
      el("p", { html: "An error in a record of a source is best also corrected at the source, so that it is right " +
        "there too and reaches confref with the next harvest. The sources and how to report to them are listed on " +
        '<a href="' + GUIDE + '"' + ext + ">www.confref.org/feedback/</a>. Missing conferences are not added in " +
        'confref: add them to <a href="' + CONFIDENT + '"' + ext + ">ConfIDent</a>, and they reach confref from there." }),
      el("ol", {}, [
        el("li", { text: "Select on the page the text your feedback is about. You can do that while this panel is open; it is optional." }),
        el("li", { text: "Describe what is wrong and, if you know, what it should be." }),
        el("li", { html: "Open the prepared issue on GitHub (you need a GitHub account), or copy the text and send it to " +
          'the <a href="' + CONTACT + '"' + ext + ">contact</a> of the project, or keep it." }),
      ]),
      el("p", { class: "cr-fb-hint", text: "Nothing is sent until you submit it on GitHub yourself." }),
    ]);
    var start = el("button", { type: "button", class: "cr-fb-primary", text: "Start" });
    start.addEventListener("click", function () { step(2); field("description").focus(); });
    intro.append(start);

    var iri = el("input", { name: "cr-fb-iri", type: "text", spellcheck: "false" });
    var page = el("input", { name: "cr-fb-page", type: "text", readonly: "" });
    var quote = el("textarea", { name: "cr-fb-quote", rows: "3", placeholder: "Select text on the page …" });
    var desc = el("textarea", { name: "cr-fb-description", rows: "5", required: "" });
    var title = el("input", { name: "cr-fb-title", type: "text" });
    var full = el("textarea", { name: "cr-fb-full", rows: "6", readonly: "" });
    var open = el("a", { class: "cr-fb-primary", target: "_blank", rel: "noopener", text: "Open the issue on GitHub" });
    var copy = el("button", { type: "button", class: "cr-fb-secondary", text: "Copy the text" });
    var status = el("p", { class: "cr-fb-status", role: "status" });
    copy.addEventListener("click", function () {
      var text = field("full").value;
      var done = function () { status.textContent = "Copied. Paste it into an e-mail to the project, or keep it."; };
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, select);
      else select();
      function select() { field("full").select(); document.execCommand("copy"); done(); }
    });
    open.addEventListener("click", function (ev) { if (!field("description").value.trim()) { ev.preventDefault(); desc.focus(); } });
    [iri, quote, desc, title].forEach(function (c) { c.addEventListener("input", update); });
    var form = el("div", { class: "cr-fb-step", "data-step": "2", hidden: "" }, [
      labelled("About", iri, "The resource your feedback is about, found on the page; change it if needed."),
      labelled("Selected text", quote, "Select text on the page to take it here, or type it."),
      labelled("Your feedback", desc, "What is wrong, and what should it be? Sources help."),
      labelled("Subject", title),
      labelled("Page", page),
      el("div", { class: "cr-fb-actions" }, [open, copy]),
      status,
      el("details", { class: "cr-fb-more" }, [el("summary", { text: "The whole text, to copy or keep" }), full,
        el("p", { class: "cr-fb-hint", html: 'Without a GitHub account: send it to the <a href="' + CONTACT +
          '" target="_blank" rel="noopener">contact</a> of the project.' })]),
    ]);
    panel.append(el("div", { class: "cr-fb-head" }, [el("h2", { id: "cr-fb-title", text: "Feedback on the data" }), close]),
      intro, form);
    panel.addEventListener("keydown", function (ev) { if (ev.key === "Escape") hide(); });
    document.body.append(panel);
  }
  function step(n) {
    panel.querySelectorAll(".cr-fb-step").forEach(function (s) { s.hidden = s.getAttribute("data-step") !== String(n); });
  }
  function texts() {
    var iri = field("iri").value.trim(), quote = field("quote").value.trim(), desc = field("description").value.trim();
    var page = field("page").value, title = field("title").value.trim() || "Feedback on the data";
    var body = ["About: " + (iri || "–"), "Page: " + page, "", "Selected text:", quote ? "> " + quote.replace(/\n/g, "\n> ") : "–",
      "", "Feedback:", desc || "–"].join("\n");
    return { iri: iri, quote: quote, desc: desc, page: page, title: title, body: body };
  }
  function issueUrl(t, short) {
    var q = new URLSearchParams({ template: "feedback.yml", title: t.title, iri: t.iri, page: t.page,
      quote: short ? t.quote.slice(0, 300) + (t.quote.length > 300 ? " …" : "") : t.quote, description: t.desc });
    return REPO + "/issues/new?" + q.toString();
  }
  function update() {
    var t = texts();
    field("full").value = "Subject: " + t.title + "\n\n" + t.body;
    var url = issueUrl(t, false);
    if (url.length > MAX_URL) url = issueUrl(t, true);
    var a = panel.querySelector("a.cr-fb-primary");
    a.href = url;
    a.setAttribute("aria-disabled", t.desc ? "false" : "true");
    try { sessionStorage.setItem(KEY, JSON.stringify({ desc: field("description").value, quote: field("quote").value,
      iri: field("iri").value, title: field("title").value })); } catch (e) { /* storage may be blocked */ }
  }
  var opener = null;
  function show(ev) {
    if (ev) ev.preventDefault();
    opener = ev && ev.currentTarget;
    if (!panel) build();
    var saved = null;
    try { saved = JSON.parse(sessionStorage.getItem(KEY) || "null"); } catch (e) { saved = null; }
    field("page").value = location.href;
    field("iri").value = (saved && saved.iri) || pageSubject();
    field("quote").value = (saved && saved.quote) || "";
    field("description").value = (saved && saved.desc) || "";
    field("title").value = (saved && saved.title) || ("Feedback: " + (document.title || location.pathname).split(" · ")[0]);
    panel.hidden = false;
    step(saved && saved.desc ? 2 : 1);
    update();
    (panel.querySelector(".cr-fb-step:not([hidden]) .cr-fb-primary") || panel).focus();
  }
  function hide() {
    if (!panel) return;
    panel.hidden = true;
    if (opener && opener.focus) opener.focus();
  }
  function wire() {
    document.querySelectorAll("[data-cr-feedback]").forEach(function (b) {
      if (!b.crFeedback) { b.crFeedback = true; b.addEventListener("click", show); }
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire); else wire();
})();
