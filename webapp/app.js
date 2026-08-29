(function () {
  "use strict";

  var tg = window.Telegram && window.Telegram.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
  }

  var STORAGE_KEY = "patientnote_smp_history_v1";

  var state = {
    data: null,
    activeTab: "emergency", // "emergency" | "reanimation"
    searchQuery: "",
    view: "list", // "list" | "detail" | "history"
    currentItem: null, // { source: "emergency"|"reanimation"|"history", id, name, mkb, fields }
  };

  var el = {
    topbarTitle: document.getElementById("topbarTitle"),
    historyBtn: document.getElementById("historyBtn"),
    tabs: document.getElementById("tabs"),
    searchRow: document.getElementById("searchRow"),
    searchInput: document.getElementById("searchInput"),
    listView: document.getElementById("listView"),
    detailView: document.getElementById("detailView"),
    historyView: document.getElementById("historyView"),
    detailTitle: document.getElementById("detailTitle"),
    detailMkb: document.getElementById("detailMkb"),
    detailFields: document.getElementById("detailFields"),
    backBtn: document.getElementById("backBtn"),
    historyBackBtn: document.getElementById("historyBackBtn"),
    copyBtn: document.getElementById("copyBtn"),
    saveBtn: document.getElementById("saveBtn"),
    historyList: document.getElementById("historyList"),
    toast: document.getElementById("toast"),
  };

  // ---------------- Data loading ----------------

  fetch("data.json")
    .then(function (r) { return r.json(); })
    .then(function (json) {
      state.data = json;
      renderList();
    })
    .catch(function () {
      el.listView.innerHTML = '<div class="empty-state">Не удалось загрузить базу диагнозов (data.json). Проверьте, что файл лежит рядом с index.html.</div>';
    });

  // ---------------- Tabs ----------------

  el.tabs.addEventListener("click", function (e) {
    var btn = e.target.closest(".tab");
    if (!btn) return;
    Array.prototype.forEach.call(el.tabs.querySelectorAll(".tab"), function (t) {
      t.classList.toggle("active", t === btn);
    });
    state.activeTab = btn.getAttribute("data-tab");
    el.topbarTitle.textContent = state.activeTab === "emergency" ? "Карта СМП" : "Реанимация";
    renderList();
  });

  // ---------------- Search ----------------

  el.searchInput.addEventListener("input", function () {
    state.searchQuery = el.searchInput.value.trim().toLowerCase();
    renderList();
  });

  // ---------------- List rendering ----------------

  function currentDataset() {
    if (!state.data) return [];
    return state.activeTab === "emergency" ? state.data.emergency : state.data.reanimation;
  }

  function renderList() {
    var items = currentDataset();
    var q = state.searchQuery;

    if (q) {
      items = items.filter(function (it) {
        return it.name.toLowerCase().indexOf(q) !== -1 ||
               (it.mkb || "").toLowerCase().indexOf(q) !== -1;
      });
    }

    if (!items.length) {
      el.listView.innerHTML = '<div class="empty-state">Ничего не найдено</div>';
      return;
    }

    var html = "";
    for (var i = 0; i < items.length; i++) {
      var it = items[i];
      html += '<div class="list-item" data-id="' + it.id + '">' +
        '<span class="list-item-name">' + escapeHtml(it.name) + '</span>' +
        (it.mkb ? '<span class="mkb-pill">' + escapeHtml(it.mkb) + '</span>' : '') +
        '</div>';
    }
    el.listView.innerHTML = html;
  }

  el.listView.addEventListener("click", function (e) {
    var row = e.target.closest(".list-item");
    if (!row) return;
    var id = Number(row.getAttribute("data-id"));
    var items = currentDataset();
    var item = items.find(function (it) { return it.id === id; });
    if (!item) return;
    openDetail({
      source: state.activeTab,
      id: item.id,
      name: item.name,
      mkb: item.mkb,
      fields: Object.assign({}, item.fields),
    });
  });

  // ---------------- Detail view ----------------

  function fieldGroupsFor(source) {
    if (source === "emergency") {
      return [{ title: null, fields: state.data.emergencyFields }];
    }
    // reanimation: clinical picture + CPR protocol
    return [
      { title: "Клиническая картина", fields: state.data.emergencyFields },
      { title: "Протокол сердечно-лёгочной реанимации", fields: state.data.reanimationFields },
    ];
  }

  function openDetail(item) {
    state.currentItem = item;
    state.view = "detail";

    el.detailTitle.textContent = item.name;
    el.detailMkb.textContent = item.mkb || "";
    el.detailMkb.style.display = item.mkb ? "" : "none";

    var groups = fieldGroupsFor(item.source === "history" ? item.origin : item.source);
    var html = "";
    groups.forEach(function (group) {
      if (group.title) {
        html += '<div class="field-group-title">' + escapeHtml(group.title) + '</div>';
      }
      group.fields.forEach(function (pair) {
        var key = pair[0], label = pair[1];
        var value = item.fields[key] || "";
        html += '<div class="field-group">' +
          '<label class="field-label" for="f_' + key + '">' + escapeHtml(label) + '</label>' +
          '<textarea class="field-textarea" id="f_' + key + '" data-key="' + key + '">' + escapeHtml(value) + '</textarea>' +
          '</div>';
      });
    });
    el.detailFields.innerHTML = html;

    el.listView.classList.add("hidden");
    el.historyView.classList.add("hidden");
    el.searchRow.classList.add("hidden");
    el.tabs.classList.add("hidden");
    el.detailView.classList.remove("hidden");

    window.scrollTo(0, 0);
  }

  function collectFieldsFromForm() {
    var fields = {};
    Array.prototype.forEach.call(el.detailFields.querySelectorAll(".field-textarea"), function (ta) {
      fields[ta.getAttribute("data-key")] = ta.value;
    });
    return fields;
  }

  function closeDetail() {
    state.view = "list";
    state.currentItem = null;
    el.detailView.classList.add("hidden");
    el.searchRow.classList.remove("hidden");
    el.tabs.classList.remove("hidden");
    el.listView.classList.remove("hidden");
  }

  el.backBtn.addEventListener("click", closeDetail);

  // ---------------- Build printable / copyable text ----------------

  function buildCardText(item, fields) {
    var lines = [];
    lines.push(item.name + (item.mkb ? " (код по МКБ: " + item.mkb + ")" : ""));
    lines.push("");

    var source = item.source === "history" ? item.origin : item.source;
    var groups = fieldGroupsFor(source);
    groups.forEach(function (group) {
      if (group.title) {
        lines.push("== " + group.title + " ==");
        lines.push("");
      }
      group.fields.forEach(function (pair) {
        var key = pair[0], label = pair[1];
        var value = (fields[key] || "").trim();
        lines.push(label + ":");
        lines.push(value || "—");
        lines.push("");
      });
    });

    return lines.join("\n").trim();
  }

  el.copyBtn.addEventListener("click", function () {
    if (!state.currentItem) return;
    var fields = collectFieldsFromForm();
    var text = buildCardText(state.currentItem, fields);

    var done = function () {
      showToast("Карта скопирована");
      if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
    };

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(function () {
        fallbackCopy(text);
        done();
      });
    } else {
      fallbackCopy(text);
      done();
    }
  });

  function fallbackCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e) { /* noop */ }
    document.body.removeChild(ta);
  }

  // ---------------- Save to history (localStorage) ----------------

  function loadHistory() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    } catch (e) {
      return [];
    }
  }

  function persistHistory(list) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
      return true;
    } catch (e) {
      return false;
    }
  }

  el.saveBtn.addEventListener("click", function () {
    if (!state.currentItem) return;
    var fields = collectFieldsFromForm();
    var item = state.currentItem;
    var origin = item.source === "history" ? item.origin : item.source;

    var entry = {
      historyId: "h_" + Date.now(),
      origin: origin,
      name: item.name,
      mkb: item.mkb,
      fields: fields,
      savedAt: new Date().toLocaleString("ru-RU"),
    };

    var list = loadHistory();
    list.unshift(entry);
    var ok = persistHistory(list);

    if (ok) {
      showToast("Карта сохранена в историю");
      if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
    } else {
      showToast("Не удалось сохранить — нет места в хранилище");
    }
  });

  // ---------------- History view ----------------

  el.historyBtn.addEventListener("click", function () {
    state.view = "history";
    el.listView.classList.add("hidden");
    el.detailView.classList.add("hidden");
    el.searchRow.classList.add("hidden");
    el.tabs.classList.add("hidden");
    el.historyView.classList.remove("hidden");
    renderHistory();
  });

  el.historyBackBtn.addEventListener("click", function () {
    state.view = "list";
    el.historyView.classList.add("hidden");
    el.searchRow.classList.remove("hidden");
    el.tabs.classList.remove("hidden");
    el.listView.classList.remove("hidden");
  });

  function renderHistory() {
    var list = loadHistory();
    if (!list.length) {
      el.historyList.innerHTML = '<div class="empty-state">Пока нет сохранённых карт</div>';
      return;
    }
    var html = "";
    list.forEach(function (entry) {
      html += '<div class="history-item" data-id="' + entry.historyId + '">' +
        '<button class="history-item-delete" data-delete="' + entry.historyId + '">Удалить</button>' +
        '<div class="history-item-name">' + escapeHtml(entry.name) + '</div>' +
        '<div class="history-item-meta">' + escapeHtml(entry.savedAt) +
        (entry.mkb ? " · " + escapeHtml(entry.mkb) : "") + '</div>' +
        '</div>';
    });
    el.historyList.innerHTML = html;
  }

  el.historyList.addEventListener("click", function (e) {
    var delBtn = e.target.closest("[data-delete]");
    if (delBtn) {
      var id = delBtn.getAttribute("data-delete");
      var list = loadHistory().filter(function (x) { return x.historyId !== id; });
      persistHistory(list);
      renderHistory();
      return;
    }
    var row = e.target.closest(".history-item");
    if (!row) return;
    var hid = row.getAttribute("data-id");
    var entry = loadHistory().find(function (x) { return x.historyId === hid; });
    if (!entry) return;
    openDetail({
      source: "history",
      origin: entry.origin,
      id: entry.historyId,
      name: entry.name,
      mkb: entry.mkb,
      fields: Object.assign({}, entry.fields),
    });
  });

  // ---------------- Utils ----------------

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  var toastTimer = null;
  function showToast(msg) {
    el.toast.textContent = msg;
    el.toast.classList.add("show");
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      el.toast.classList.remove("show");
    }, 2200);
  }
})();
