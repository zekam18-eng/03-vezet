(function () {
  "use strict";

  var tg = window.Telegram && window.Telegram.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
  }

  var LS_HISTORY = "patientnote_smp_history_v1";
  var LS_REANIMATION = "pn_local_reanimation_v1";
  var LS_LOCAL_STATUS = "pn_local_status_v1";

  var state = {
    data: null,
    activeTab: "emergency", // "emergency" | "reanimation" | "localStatus" | "lookup"
    searchQuery: "",
    view: "list", // "list" | "detail" | "history"
    currentItem: null,
    gridColCount: 35,
  };

  var el = {
    topbarTitle: document.getElementById("topbarTitle"),
    addBtn: document.getElementById("addBtn"),
    historyBtn: document.getElementById("historyBtn"),
    tabs: document.getElementById("tabs"),
    searchRow: document.getElementById("searchRow"),
    searchInput: document.getElementById("searchInput"),
    listView: document.getElementById("listView"),
    detailView: document.getElementById("detailView"),
    historyView: document.getElementById("historyView"),
    lookupView: document.getElementById("lookupView"),
    detailTitle: document.getElementById("detailTitle"),
    detailMkb: document.getElementById("detailMkb"),
    detailFields: document.getElementById("detailFields"),
    backBtn: document.getElementById("backBtn"),
    historyBackBtn: document.getElementById("historyBackBtn"),
    copyBtn: document.getElementById("copyBtn"),
    saveBtn: document.getElementById("saveBtn"),
    historyList: document.getElementById("historyList"),
    toast: document.getElementById("toast"),
    lookupInput: document.getElementById("lookupInput"),
    lookupBtn: document.getElementById("lookupBtn"),
    lookupNote: document.getElementById("lookupNote"),
  };

  var TAB_TITLES = {
    emergency: "Карта СМП",
    reanimation: "Реанимация",
    localStatus: "Локальный статус",
    lookup: "Подкрадули",
  };

  // ---------------- Data loading ----------------

  fetch("data.json")
    .then(function (r) { return r.json(); })
    .then(function (json) {
      state.data = json;
      renderList();
    })
    .catch(function () {
      el.listView.innerHTML = '<div class="empty-state">Не удалось загрузить базу (data.json). Проверьте, что файл лежит рядом с index.html.</div>';
    });

  // ---------------- localStorage helpers ----------------

  function loadMap(key) {
    try {
      return JSON.parse(localStorage.getItem(key) || "{}");
    } catch (e) {
      return {};
    }
  }

  function saveMap(key, map) {
    try {
      localStorage.setItem(key, JSON.stringify(map));
      return true;
    } catch (e) {
      return false;
    }
  }

  function loadHistory() {
    try {
      return JSON.parse(localStorage.getItem(LS_HISTORY) || "[]");
    } catch (e) {
      return [];
    }
  }

  function saveHistory(list) {
    try {
      localStorage.setItem(LS_HISTORY, JSON.stringify(list));
      return true;
    } catch (e) {
      return false;
    }
  }

  // ---------------- Merged lists (base data + local overlay) ----------------

  function getReanimationList() {
    var overrides = loadMap(LS_REANIMATION);
    var base = (state.data.reanimation || []).map(function (item) {
      var ov = overrides[String(item.id)];
      return ov ? Object.assign({}, item, ov, { id: item.id }) : item;
    });
    var baseIds = {};
    base.forEach(function (it) { baseIds[String(it.id)] = true; });
    var extra = Object.keys(overrides)
      .filter(function (k) { return !baseIds[k]; })
      .map(function (k) { return overrides[k]; });
    return base.concat(extra);
  }

  function getLocalStatusList() {
    var overrides = loadMap(LS_LOCAL_STATUS);
    var base = (state.data.localStatus || []).map(function (item) {
      var ov = overrides[String(item.id)];
      return ov ? Object.assign({}, item, ov, { id: item.id }) : item;
    });
    var baseIds = {};
    base.forEach(function (it) { baseIds[String(it.id)] = true; });
    var extra = Object.keys(overrides)
      .filter(function (k) { return !baseIds[k]; })
      .map(function (k) { return overrides[k]; });
    return base.concat(extra);
  }

  function currentDataset() {
    if (!state.data) return [];
    if (state.activeTab === "emergency") return state.data.emergency;
    if (state.activeTab === "reanimation") return getReanimationList();
    if (state.activeTab === "localStatus") return getLocalStatusList();
    return [];
  }

  // ---------------- Tabs ----------------

  el.tabs.addEventListener("click", function (e) {
    var btn = e.target.closest(".tab");
    if (!btn) return;
    Array.prototype.forEach.call(el.tabs.querySelectorAll(".tab"), function (t) {
      t.classList.toggle("active", t === btn);
    });
    state.activeTab = btn.getAttribute("data-tab");
    el.topbarTitle.textContent = TAB_TITLES[state.activeTab];

    var isLookup = state.activeTab === "lookup";
    el.addBtn.classList.toggle("hidden", isLookup || state.activeTab === "emergency");
    el.historyBtn.classList.toggle("hidden", state.activeTab !== "emergency");
    el.searchRow.classList.toggle("hidden", isLookup);

    el.listView.classList.toggle("hidden", isLookup);
    el.lookupView.classList.toggle("hidden", !isLookup);
    el.detailView.classList.add("hidden");
    el.historyView.classList.add("hidden");

    if (!isLookup) renderList();
  });

  // ---------------- Search ----------------

  el.searchInput.addEventListener("input", function () {
    state.searchQuery = el.searchInput.value.trim().toLowerCase();
    renderList();
  });

  // ---------------- List rendering ----------------

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
    var id = row.getAttribute("data-id");
    var items = currentDataset();
    var item = items.find(function (it) { return String(it.id) === String(id); });
    if (!item) return;
    openDetail(item);
  });

  // ---------------- Add new item ----------------

  el.addBtn.addEventListener("click", function () {
    if (state.activeTab === "reanimation") addReanimationCase();
    if (state.activeTab === "localStatus") addLocalStatusCase();
  });

  function addReanimationCase() {
    var name = window.prompt("Название/диагноз случая:");
    if (name === null) return;
    name = name.trim();
    if (!name) { showToast("Введите название"); return; }
    var mkb = window.prompt("Код по МКБ (можно оставить пустым):") || "";
    mkb = mkb.trim();

    var id = "local_" + Date.now();
    var newCase = {
      id: id, name: name, mkb: mkb,
      clinicalFields: {},
      protocolData: buildEmptyProtocolData(),
    };

    var overrides = loadMap(LS_REANIMATION);
    overrides[id] = newCase;
    saveMap(LS_REANIMATION, overrides);

    state.searchQuery = "";
    el.searchInput.value = "";
    renderList();
    openDetail(newCase);
  }

  function addLocalStatusCase() {
    var name = window.prompt("Название диагноза:");
    if (name === null) return;
    name = name.trim();
    if (!name) { showToast("Введите название"); return; }
    var mkb = window.prompt("Код по МКБ (можно оставить пустым):") || "";
    mkb = mkb.trim();

    var id = "local_" + Date.now();
    var newCase = { id: id, name: name, mkb: mkb, text: "" };

    var overrides = loadMap(LS_LOCAL_STATUS);
    overrides[id] = newCase;
    saveMap(LS_LOCAL_STATUS, overrides);

    state.searchQuery = "";
    el.searchInput.value = "";
    renderList();
    openDetail(newCase);
  }

  function buildEmptyProtocolData() {
    var result = {};
    state.data.protocolSections.forEach(function (section) {
      var key = section[0], fields = section[2];
      result[key] = {};
      fields.forEach(function (f) { result[key][f[0]] = ""; });
    });
    result.grid_compressions = emptyGrid(state.data.compressionGridRows.length);
    result.grid_ecg = emptyGrid(state.data.ecgGridRows.length);
    result.grid_meds = emptyGrid(state.data.medicationGridRows.length);
    return result;
  }

  function emptyGrid(rowCount, cols) {
    cols = cols || 35;
    var columns = [];
    for (var i = 1; i <= cols; i++) columns.push(String(i));
    var cells = [];
    for (var r = 0; r < rowCount; r++) cells.push(new Array(cols).fill(""));
    return { columns: columns, cells: cells };
  }

  // ---------------- Detail view: routing by tab ----------------

  function openDetail(item) {
    state.currentItem = item;
    state.view = "detail";

    el.detailTitle.textContent = item.name;
    el.detailMkb.textContent = item.mkb || "";
    el.detailMkb.style.display = item.mkb ? "" : "none";

    if (state.activeTab === "emergency") {
      renderEmergencyDetail(item);
      el.saveBtn.textContent = "Сохранить в историю";
    } else if (state.activeTab === "reanimation") {
      renderReanimationDetail(item);
      el.saveBtn.textContent = "Сохранить случай";
    } else if (state.activeTab === "localStatus") {
      renderLocalStatusDetail(item);
      el.saveBtn.textContent = "Сохранить";
    }

    el.listView.classList.add("hidden");
    el.historyView.classList.add("hidden");
    el.searchRow.classList.add("hidden");
    el.tabs.classList.add("hidden");
    el.detailView.classList.remove("hidden");

    window.scrollTo(0, 0);
  }

  function closeDetail() {
    state.view = "list";
    state.currentItem = null;
    el.detailView.classList.add("hidden");
    if (state.activeTab !== "lookup") el.searchRow.classList.remove("hidden");
    el.tabs.classList.remove("hidden");
    el.listView.classList.remove("hidden");
  }

  el.backBtn.addEventListener("click", closeDetail);

  // ---------------- Emergency detail ----------------

  function renderEmergencyDetail(item) {
    var html = "";
    state.data.emergencyFields.forEach(function (pair) {
      var key = pair[0], label = pair[1];
      var value = (item.fields && item.fields[key]) || "";
      html += '<div class="field-group">' +
        '<label class="field-label">' + escapeHtml(label) + '</label>' +
        '<textarea class="field-textarea" data-key="' + key + '">' + escapeHtml(value) + '</textarea>' +
        '</div>';
    });
    el.detailFields.innerHTML = html;
  }

  function collectEmergencyFields() {
    var fields = {};
    Array.prototype.forEach.call(el.detailFields.querySelectorAll(".field-textarea[data-key]"), function (ta) {
      fields[ta.getAttribute("data-key")] = ta.value;
    });
    return fields;
  }

  // ---------------- Local status detail ----------------

  function renderLocalStatusDetail(item) {
    el.detailFields.innerHTML =
      '<div class="field-group">' +
      '<label class="field-label">Локальный статус</label>' +
      '<textarea class="field-textarea" id="localStatusText" style="min-height:200px;">' + escapeHtml(item.text || "") + '</textarea>' +
      '</div>';
  }

  // ---------------- Reanimation detail (protocol sections + grids) ----------------

  function renderReanimationDetail(item) {
    var clinicalFields = item.clinicalFields || {};
    var protocolData = item.protocolData || buildEmptyProtocolData();

    state.gridColCount = (protocolData.grid_compressions && protocolData.grid_compressions.columns.length) || 35;

    var html = '<div class="section-title">Клиническая картина</div>';
    state.data.emergencyFields.forEach(function (pair) {
      var key = pair[0], label = pair[1];
      var value = clinicalFields[key] || "";
      html += '<div class="field-group">' +
        '<label class="field-label">' + escapeHtml(label) + '</label>' +
        '<textarea class="field-textarea" data-clinical-key="' + key + '">' + escapeHtml(value) + '</textarea>' +
        '</div>';
    });

    html += '<div class="section-title">Протокол сердечно-лёгочной реанимации</div>';

    state.data.protocolSections.forEach(function (section) {
      var sectionKey = section[0], sectionTitle = section[1], fields = section[2];
      var sectionData = protocolData[sectionKey] || {};

      html += '<div class="protocol-box"><div class="protocol-box-title">' + escapeHtml(sectionTitle) + '</div>';

      fields.forEach(function (spec) {
        var fieldKey = spec[0], fieldLabel = spec[1], fieldType = spec[2];
        var value = sectionData[fieldKey] || "";

        html += '<label class="field-label">' + escapeHtml(fieldLabel) + '</label>';
        if (fieldType === "combo") {
          var options = spec[3] || [];
          html += '<select class="field-select" data-proto-section="' + sectionKey + '" data-proto-field="' + fieldKey + '">';
          html += '<option value=""' + (value === "" ? " selected" : "") + '></option>';
          options.forEach(function (opt) {
            html += '<option value="' + escapeAttr(opt) + '"' + (opt === value ? " selected" : "") + '>' + escapeHtml(opt) + '</option>';
          });
          html += '</select>';
        } else {
          html += '<input type="text" class="field-input" data-proto-section="' + sectionKey + '" data-proto-field="' + fieldKey + '" value="' + escapeAttr(value) + '">';
        }
      });

      html += '</div>';

      if (sectionKey === "chronometry_header") {
        html += '<div class="field-label">Хронометраж (компрессии, ИВЛ) — по минутам</div>';
        html += '<div id="gridCompressionsContainer">' +
          buildGridHtml("compressions", state.data.compressionGridRows, protocolData.grid_compressions.cells, state.gridColCount) +
          '</div>';
      }
      if (sectionKey === "defibrillator_header") {
        html += '<div class="field-label">Ритм / дефибрилляция — по минутам</div>';
        html += '<div id="gridEcgContainer">' +
          buildGridHtml("ecg", state.data.ecgGridRows, protocolData.grid_ecg.cells, state.gridColCount) +
          '</div>';
      }
      if (sectionKey === "medication_header") {
        html += '<div class="field-label">Медикаменты — по минутам</div>';
        html += '<div id="gridMedsContainer">' +
          buildGridHtml("meds", state.data.medicationGridRows, protocolData.grid_meds.cells, state.gridColCount) +
          '</div>';
      }
    });

    html += '<button class="add-minute-btn" id="addMinuteBtn">+ Добавить минуту (во все таблицы)</button>';

    el.detailFields.innerHTML = html;

    document.getElementById("addMinuteBtn").addEventListener("click", addMinuteColumn);
  }

  function buildGridHtml(gridName, rowLabels, cellsData, colCount) {
    var theadCells = "<th></th>";
    for (var c = 1; c <= colCount; c++) theadCells += "<th>" + c + "</th>";

    var rowsHtml = "";
    rowLabels.forEach(function (label, r) {
      var rowCells = '<td class="row-label">' + escapeHtml(label) + '</td>';
      for (var c = 0; c < colCount; c++) {
        var val = (cellsData[r] && cellsData[r][c]) || "";
        rowCells += '<td><input type="text" data-grid="' + gridName + '" data-row="' + r + '" value="' + escapeAttr(val) + '"></td>';
      }
      rowsHtml += "<tr>" + rowCells + "</tr>";
    });

    return '<div class="grid-scroll"><table class="grid-table"><thead><tr>' + theadCells +
      '</tr></thead><tbody>' + rowsHtml + '</tbody></table></div>';
  }

  function collectGridCells(gridName, rowCount) {
    var cells = [];
    for (var r = 0; r < rowCount; r++) {
      var row = [];
      var inputs = el.detailFields.querySelectorAll('[data-grid="' + gridName + '"][data-row="' + r + '"]');
      Array.prototype.forEach.call(inputs, function (inp) { row.push(inp.value); });
      cells.push(row);
    }
    return cells;
  }

  function gridColumns(count) {
    var columns = [];
    for (var i = 1; i <= count; i++) columns.push(String(i));
    return columns;
  }

  function addMinuteColumn() {
    // Собираем текущие значения всех трёх таблиц перед перерисовкой,
    // чтобы не потерять уже введённые данные.
    var compressions = collectGridCells("compressions", state.data.compressionGridRows.length);
    var ecg = collectGridCells("ecg", state.data.ecgGridRows.length);
    var meds = collectGridCells("meds", state.data.medicationGridRows.length);

    state.gridColCount += 1;

    document.getElementById("gridCompressionsContainer").innerHTML =
      buildGridHtml("compressions", state.data.compressionGridRows, compressions, state.gridColCount);
    document.getElementById("gridEcgContainer").innerHTML =
      buildGridHtml("ecg", state.data.ecgGridRows, ecg, state.gridColCount);
    document.getElementById("gridMedsContainer").innerHTML =
      buildGridHtml("meds", state.data.medicationGridRows, meds, state.gridColCount);
  }

  function collectClinicalFields() {
    var fields = {};
    Array.prototype.forEach.call(el.detailFields.querySelectorAll("[data-clinical-key]"), function (ta) {
      fields[ta.getAttribute("data-clinical-key")] = ta.value;
    });
    return fields;
  }

  function collectProtocolData() {
    var result = {};
    state.data.protocolSections.forEach(function (section) {
      var sectionKey = section[0], fields = section[2];
      result[sectionKey] = {};
      fields.forEach(function (spec) {
        var fieldKey = spec[0];
        var elField = el.detailFields.querySelector(
          '[data-proto-section="' + sectionKey + '"][data-proto-field="' + fieldKey + '"]'
        );
        result[sectionKey][fieldKey] = elField ? elField.value : "";
      });
    });

    result.grid_compressions = {
      columns: gridColumns(state.gridColCount),
      cells: collectGridCells("compressions", state.data.compressionGridRows.length),
    };
    result.grid_ecg = {
      columns: gridColumns(state.gridColCount),
      cells: collectGridCells("ecg", state.data.ecgGridRows.length),
    };
    result.grid_meds = {
      columns: gridColumns(state.gridColCount),
      cells: collectGridCells("meds", state.data.medicationGridRows.length),
    };

    return result;
  }

  // ---------------- Save button: behavior depends on active tab ----------------

  el.saveBtn.addEventListener("click", function () {
    if (!state.currentItem) return;

    if (state.activeTab === "emergency") {
      saveEmergencyToHistory();
    } else if (state.activeTab === "reanimation") {
      saveReanimationCase();
    } else if (state.activeTab === "localStatus") {
      saveLocalStatusCase();
    }
  });

  function saveEmergencyToHistory() {
    var item = state.currentItem;
    var fields = collectEmergencyFields();

    var entry = {
      historyId: "h_" + Date.now(),
      origin: "emergency",
      name: item.name,
      mkb: item.mkb,
      fields: fields,
      savedAt: new Date().toLocaleString("ru-RU"),
    };

    var list = loadHistory();
    list.unshift(entry);
    var ok = saveHistory(list);

    if (ok) {
      showToast("Карта сохранена в историю");
      if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
    } else {
      showToast("Не удалось сохранить — нет места в хранилище");
    }
  }

  function saveReanimationCase() {
    var item = state.currentItem;
    var clinicalFields = collectClinicalFields();
    var protocolData = collectProtocolData();

    var overrides = loadMap(LS_REANIMATION);
    overrides[String(item.id)] = {
      id: item.id, name: item.name, mkb: item.mkb,
      clinicalFields: clinicalFields, protocolData: protocolData,
    };
    var ok = saveMap(LS_REANIMATION, overrides);

    if (ok) {
      showToast("Случай сохранён");
      if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
    } else {
      showToast("Не удалось сохранить — нет места в хранилище");
    }
  }

  function saveLocalStatusCase() {
    var item = state.currentItem;
    var textEl = document.getElementById("localStatusText");
    var text = textEl ? textEl.value : "";

    var overrides = loadMap(LS_LOCAL_STATUS);
    overrides[String(item.id)] = { id: item.id, name: item.name, mkb: item.mkb, text: text };
    var ok = saveMap(LS_LOCAL_STATUS, overrides);

    if (ok) {
      showToast("Сохранено");
      if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
    } else {
      showToast("Не удалось сохранить — нет места в хранилище");
    }
  }

  // ---------------- Copy button: builds plain text for the active tab ----------------

  el.copyBtn.addEventListener("click", function () {
    if (!state.currentItem) return;
    var text = buildCopyText();
    var done = function () {
      showToast("Скопировано");
      if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(function () { fallbackCopy(text); done(); });
    } else {
      fallbackCopy(text);
      done();
    }
  });

  function buildCopyText() {
    var item = state.currentItem;
    var lines = [item.name + (item.mkb ? " (код по МКБ: " + item.mkb + ")" : ""), ""];

    if (state.activeTab === "emergency") {
      var fields = collectEmergencyFields();
      state.data.emergencyFields.forEach(function (pair) {
        lines.push(pair[1] + ":");
        lines.push((fields[pair[0]] || "").trim() || "—");
        lines.push("");
      });
    } else if (state.activeTab === "localStatus") {
      var textEl = document.getElementById("localStatusText");
      lines.push((textEl ? textEl.value : "").trim() || "—");
    } else if (state.activeTab === "reanimation") {
      var clinicalFields = collectClinicalFields();
      lines.push("== Клиническая картина ==", "");
      state.data.emergencyFields.forEach(function (pair) {
        lines.push(pair[1] + ":");
        lines.push((clinicalFields[pair[0]] || "").trim() || "—");
        lines.push("");
      });
      lines.push("== Протокол СЛР ==", "");
      state.data.protocolSections.forEach(function (section) {
        var sectionKey = section[0], sectionTitle = section[1], fields = section[2];
        lines.push(sectionTitle + ":");
        fields.forEach(function (spec) {
          var fieldKey = spec[0], fieldLabel = spec[1];
          var elField = el.detailFields.querySelector(
            '[data-proto-section="' + sectionKey + '"][data-proto-field="' + fieldKey + '"]'
          );
          var val = elField ? elField.value : "";
          if (val) lines.push("  " + fieldLabel + ": " + val);
        });
        lines.push("");
      });
    }

    return lines.join("\n").trim();
  }

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

  // ---------------- History view (emergency only) ----------------

  el.historyBtn.addEventListener("click", function () {
    if (state.activeTab !== "emergency") return;
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
      saveHistory(list);
      renderHistory();
      return;
    }
    var row = e.target.closest(".history-item");
    if (!row) return;
    var hid = row.getAttribute("data-id");
    var entry = loadHistory().find(function (x) { return x.historyId === hid; });
    if (!entry) return;
    state.activeTab = "emergency";
    openDetail({ id: entry.historyId, name: entry.name, mkb: entry.mkb, fields: entry.fields });
  });

  // ---------------- Lookup tab (наряд → карта) ----------------

  el.lookupBtn.addEventListener("click", openCardByNaряд);
  el.lookupInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter") openCardByNaряд();
  });

  function openCardByNaряд() {
    var raw = el.lookupInput.value.trim();
    var naряд = raw.replace(/\D/g, "");

    if (!naряд) {
      el.lookupNote.textContent = "Введите номер наряда (только цифры).";
      return;
    }

    var url = "http://212.45.19.34:8081/ekvEmc/getCardPdf.ashx?a010=" + naряд;

    if (tg && tg.openLink) {
      tg.openLink(url, { try_instant_view: false });
    } else {
      window.open(url, "_blank");
    }

    el.lookupNote.textContent =
      "Открываю карту в браузере телефона — там же можно будет выделять и копировать текст (это делает сам браузер).\n" +
      "Если ничего не открылось: сервер карт доступен только из рабочей сети/VPN — с обычного мобильного интернета до него не достучаться.";
  }

  // ---------------- Utils ----------------

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escapeAttr(str) {
    return escapeHtml(str).replace(/'/g, "&#39;");
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
