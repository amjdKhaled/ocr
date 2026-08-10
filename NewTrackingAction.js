(function () {

    "use strict";

    /* =====================================================================
     * New Tracking - Auto acknowledge, dynamic recipients, template: تتبع
     * ---------------------------------------------------------------------
     * مصدر أسماء المستلمين = حقل "المستلمون" الذي يملأه الـ Workflow.
     * لا توجد أي أسماء ثابتة داخل الكود.
     *
     * التدفق:
     *   1. الـ Workflow يكتب الأسماء في حقل "المستلمون".
     *   2. المُرسِل يضغط زر Tracking  ->  يُبنى السجل في "تتبع حالة الملف".
     *   3. كل مستلم يفتح المستند     ->  يُسجَّل اطلاعه تلقائيًا (مرة واحدة).
     * ===================================================================== */

    var config = {
        targetTemplate: "تتبع",

        /* الحقل الذي يكتب فيه الاسكريبت السجل - Text / 4000 */
        statusField: "تتبع حالة الملف الحالي",

        /* الحقل الذي يقرأ منه أسماء المستلمين - يملؤه الـ Workflow */
        recipientsField: "المستلمون",

        repoName: "Demo",

        /* لا يُسجَّل لهم اطلاع تلقائي */
        exemptUsers: ["ADMIN", "author", "workflow"],

        /* من يملك زر Tracking */
        managerUsers: ["ADMIN", "author"],

        overlayId: "newTrackOverlay",
        styleId: "newTrackOverlayStyles",
        ownerKey: "__newTrackInstance",
        checkIntervalMs: 400,
        throttleMs: 800,
        lockStatusField: true,

        /* حقول لا يعدّلها إلا من في fieldEditors - تُقفل في الواجهة للباقي.
           هذا قفل شكلي فقط؛ الحماية الحقيقية من Field Security في Admin Console. */
        protectedFields: [
            "التتبع الجديد",
            "مكان الاستلام",
            "المستلمون",
            "حاله الملف الحالي",
            "تحت المراجعة"
        ],
        fieldEditors: ["ADMIN", "author"],

        toastMs: 3500
    };

    var urls = {
        metadata: "/laserfiche/MetadataService.ashx/GetMetadata",
        lock: "/laserfiche/DocumentService.ashx/LockDocument",
        unlock: "/laserfiche/DocumentService.ashx/UnlockDocument",
        save: "/laserfiche/DocumentService.ashx/SaveEntry"
    };

    var L = {
        title: "سجل الاطلاع على المستند",
        sender: "المُرسِل",
        status: "الحالة",
        of: "من",
        done: "تم الاطلاع",
        pending: "لم يتم الاطلاع",
        none: "لا يوجد حتى الآن",
        all: "اكتمل اطلاع الجميع",
        updated: "آخر تحديث",
        rule: "──────────────────────────────────"
    };

    var LRM = "\u200E";
    var BIDI_MARKS = /[\u200E\u200F\u202A-\u202E\u2066-\u2069]/g;

    var parentWindow = window.parent || window;
    var instanceId = Date.now() + "_" + Math.random().toString(36).slice(2);
    var states = {};
    var intervalId = null;
    var saving = false;
    var managerFlowActive = false;

    /* ------------------------------------------------------------------ */
    /* أدوات عامة                                                          */
    /* ------------------------------------------------------------------ */

    function normalize(value) {
        return String(value || "").replace(BIDI_MARKS, "").trim();
    }

    function shortUser(value) {
        return normalize(value).replace(/^.*[\\\/]/, "");
    }

    function sameUser(left, right) {
        return shortUser(left).toLowerCase() === shortUser(right).toLowerCase();
    }

    function containsUser(users, userName) {
        return users.some(function (item) { return sameUser(item, userName); });
    }

    function indexOfUser(users, userName) {
        for (var i = 0; i < users.length; i++) {
            if (sameUser(users[i], userName)) return i;
        }
        return -1;
    }

    function escapeHtml(value) {
        return String(value || "").replace(/[&<>'"]/g, function (character) {
            return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character];
        });
    }

    function getLines(value) {
        var text = String(value || "");
        return text ? text.split(/\r?\n/) : [];
    }

    function splitNames(value) {
        return String(value || "")
            .split(/[;,،|\r\n]+/)
            .map(normalize)
            .filter(function (name) { return name.length > 0; });
    }

    function uniqueNames(names) {
        var out = [];
        names.forEach(function (name) {
            if (indexOfUser(out, name) === -1) out.push(name);
        });
        return out;
    }

    function formatTimestamp(date) {
        try {
            return date.toLocaleString("ar-EG-u-nu-latn", {
                day: "2-digit", month: "2-digit", year: "numeric",
                hour: "2-digit", minute: "2-digit", hour12: true
            });
        } catch (ignore) {
            return date.toLocaleString("en-US");
        }
    }

    function stampNow() {
        return normalize(formatTimestamp(new Date()));
    }

    function getCurrentUserName() {
        var selector = '[lf-bind-once="loginInfo.DisplayUser"]';
        try {
            var boundElement = parentWindow.document.querySelector(selector);
            if (boundElement && parentWindow.angular) {
                var scope = parentWindow.angular.element(boundElement).scope();
                for (var depth = 0; scope && depth < 8; depth++, scope = scope.$parent) {
                    if (scope.loginInfo && scope.loginInfo.DisplayUser) {
                        return normalize(scope.loginInfo.DisplayUser);
                    }
                }
            }
            return normalize(boundElement && (boundElement.textContent || boundElement.innerText)) || "Unknown";
        } catch (ignore) {
            return "Unknown";
        }
    }

    /**
     * اسم كوكي الـ XSRF يختلف حسب البروتوكول:
     *   https -> XSRF-TOKEN
     *   http  -> XSRF-TOKEN-HTTP
     * نجرّب الاسمين، والأنسب للبروتوكول الحالي أولًا.
     */
    function getXsrfToken() {
        var source = (window.parent && window.parent.document && window.parent !== window)
            ? window.parent.document.cookie
            : document.cookie;
        source = String(source || "");

        var names = ["XSRF-TOKEN", "XSRF-TOKEN-HTTP"];
        try {
            if (parentWindow.location.protocol === "http:") names = ["XSRF-TOKEN-HTTP", "XSRF-TOKEN"];
        } catch (ignore) { }

        for (var i = 0; i < names.length; i++) {
            var match = source.match(new RegExp("(?:^|;\\s*)" + names[i] + "=([^;]*)"));
            if (match && match[1]) return decodeURIComponent(match[1]);
        }

        if (parentWindow.console) parentWindow.console.warn("[NewTrack] لم يُعثر على كوكي XSRF.");
        return "";
    }

    function postJson(url, body) {
        return parentWindow.fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json;charset=UTF-8",
                "Lf-Repository": config.repoName,
                "X-Lf-Repo-ID": config.repoName,
                "X-XSRF-TOKEN": getXsrfToken()
            },
            body: JSON.stringify(body)
        }).then(function (response) {
            return response.text().then(function (text) {
                if (!response.ok) {
                    var detail = text ? " :: " + text.slice(0, 300) : "";
                    throw new Error("HTTP " + response.status + " calling " + url + detail);
                }
                return text ? JSON.parse(text) : null;
            });
        });
    }

    function getFocusedEntry() {
        try {
            var api = parentWindow.webAccessApi || (typeof webAccessApi !== "undefined" && webAccessApi);
            var entries = api && api.getFocusedEntries && api.getFocusedEntries();
            return entries && entries.length === 1 ? entries[0] : null;
        } catch (ignore) {
            return null;
        }
    }

    function getViewerEntryId() {
        try {
            var location = parentWindow.location;
            var source = String(location.hash || "") + "&" + String(location.search || "") + "&" + String(location.href || "");
            var match = source.match(/[?#&](?:id|entryId|docId|documentId)=(\d+)/i);
            return match ? match[1] : null;
        } catch (ignore) {
            return null;
        }
    }

    /* يقارن أسماء الحقول متجاهلًا الفرق بين ة/ه وتعدد المسافات */
    function fieldNameMatches(actual, wanted) {
        function key(value) {
            return normalize(value).replace(/\s+/g, " ").replace(/ة/g, "ه").replace(/[أإآ]/g, "ا").toLowerCase();
        }
        return key(actual) === key(wanted);
    }

    /* يقرأ الحقلين معًا في نداء واحد */
    function readFields(entryId) {
        return postJson(urls.metadata, {
            repoName: config.repoName,
            entryIds: [String(entryId)],
            metadataFlags: 1
        }).then(function (result) {
            var fields = result && result.d && result.d.Fields && result.d.Fields.templateFields;
            if (!fields) throw new Error("Laserfiche did not return templateFields.");

            var found = { status: null, recipients: null };
            for (var i = 0; i < fields.length; i++) {
                if (fieldNameMatches(fields[i].name, config.statusField)) found.status = fields[i];
                else if (fieldNameMatches(fields[i].name, config.recipientsField)) found.recipients = fields[i];
            }
            return found;
        });
    }

    /* يتعامل مع الحقل سواء كان قيمة واحدة أو متعدد القيم */
    function fieldToNames(field) {
        if (!field) return [];
        var raw = field.values || field.Values;
        if (raw && raw.length) {
            var flat = [];
            for (var i = 0; i < raw.length; i++) {
                var item = raw[i];
                flat = flat.concat(splitNames(item && item.value !== undefined ? item.value : item));
            }
            return uniqueNames(flat);
        }
        return uniqueNames(splitNames(field.value || field.Value || ""));
    }

    function lock(entryId) {
        return postJson(urls.lock, { repoName: config.repoName, documentId: entryId, lockEfile: false, autoCheckout: false });
    }

    function unlock(entryId) {
        return postJson(urls.unlock, { repoName: config.repoName, documentId: entryId }).catch(function (error) {
            if (parentWindow.console) parentWindow.console.warn("[NewTrack] Unlock failed.", error);
        });
    }

    function save(entryId, fieldId, value) {
        return postJson(urls.save, {
            repoName: config.repoName,
            documentId: entryId,
            curPageNum: 0,
            strCurPageId: 0,
            changes: {
                dirty: true, newTemplateId: 0, removeTemplate: false,
                fieldChanges: [{ fieldId: fieldId, value: value, remove: false, fieldIndex: 0 }],
                tagChanges: [], linkChanges: []
            },
            generalchanges: [],
            annchanges: []
        });
    }

    /* ================================================================== */
    /* السجل                                                              */
    /* ================================================================== */

    function parseLedger(value) {
        var state = { armed: false, sender: "", armedAt: "", done: [], pending: [] };
        var lines = getLines(value);

        for (var i = 0; i < lines.length; i++) {
            var line = normalize(lines[i]);
            if (!line) continue;
            var m;

            m = line.match(/^(?:المُرسِل|المرسل)\s*:\s*(.+?)\s+—\s+(.+?)$/);
            if (m) { state.armed = true; state.sender = normalize(m[1]); state.armedAt = normalize(m[2]); continue; }

            m = line.match(/^✔\s*(.+?)\s+—\s+(.+?)$/);
            if (m) { state.done.push({ userName: normalize(m[1]), timestamp: normalize(m[2]) }); continue; }

            m = line.match(/^✖\s*(.+?)$/);
            if (m) { state.pending.push(normalize(m[1])); continue; }
        }
        return state;
    }

    function renderLedger(state) {
        var total = state.done.length + state.pending.length;
        var lines = [];

        lines.push(L.title);
        lines.push(L.sender + ": " + state.sender + " — " + LRM + state.armedAt + LRM);
        lines.push(L.status + ": " + LRM + state.done.length + " " + L.of + " " + total + LRM);
        lines.push(L.rule);

        lines.push(L.done + " (" + state.done.length + ")");
        if (state.done.length) {
            state.done.forEach(function (item) {
                lines.push("✔ " + item.userName + " — " + LRM + item.timestamp + LRM);
            });
        } else {
            lines.push("· " + L.none);
        }

        lines.push("");
        lines.push(L.pending + " (" + state.pending.length + ")");
        if (state.pending.length) {
            state.pending.forEach(function (name) { lines.push("✖ " + name); });
        } else {
            lines.push("· " + L.all);
        }

        lines.push(L.rule);
        lines.push(L.updated + ": " + LRM + stampNow() + LRM);
        return lines.join("\n");
    }

    /**
     * يوفّق السجل مع قائمة المستلمين الحالية:
     * - من أُضيف في الحقل ولم يكن في السجل  -> يُضاف كـ "لم يتم الاطلاع"
     * - من حُذف من الحقل                    -> يُزال من السجل
     * يحافظ على أوقات من اطّلعوا بالفعل.
     */
    function reconcile(ledger, recipients) {
        var done = ledger.done.filter(function (item) { return indexOfUser(recipients, item.userName) !== -1; });
        var pending = [];
        recipients.forEach(function (name) {
            var already = done.some(function (item) { return sameUser(item.userName, name); });
            if (!already) pending.push(name);
        });
        return { armed: ledger.armed, sender: ledger.sender, armedAt: ledger.armedAt, done: done, pending: pending };
    }

    /* ================================================================== */
    /* واجهة                                                              */
    /* ================================================================== */

    function ensureStyles() {
        var doc = parentWindow.document;
        if (doc.getElementById(config.styleId)) return;
        var style = doc.createElement("style");
        style.id = config.styleId;
        style.textContent =
            "@keyframes ackSpin{to{transform:rotate(360deg)}}" +
            "@keyframes ackIn{from{opacity:0;transform:translateY(-10px)}to{opacity:1;transform:none}}" +
            "#" + config.overlayId + "{position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;justify-content:center;background:rgba(2,6,23,.9);backdrop-filter:blur(6px);font-family:'Segoe UI',Tahoma,Arial,sans-serif}" +
            "#" + config.overlayId + " .box{direction:rtl;width:min(420px,calc(100vw - 48px));padding:32px;background:#fff;border-radius:16px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.45)}" +
            "#" + config.overlayId + " .badge{display:flex;align-items:center;justify-content:center;width:52px;height:52px;margin:0 auto 16px;border-radius:50%;color:#fff;background:#2563eb;font-size:24px}" +
            "#" + config.overlayId + " .spinner{width:22px;height:22px;border:3px solid rgba(255,255,255,.35);border-top-color:#fff;border-radius:50%;animation:ackSpin .8s linear infinite}" +
            "#" + config.overlayId + " .title{font-size:18px;font-weight:700;color:#0f172a}" +
            "#" + config.overlayId + " .msg{margin:8px 0 16px;white-space:pre-line;line-height:1.7;color:#475569}" +
            "#" + config.overlayId + " .doc{display:block;color:#1e40af;font-weight:700;margin-top:4px}" +
            "#" + config.overlayId + " .names{width:100%;box-sizing:border-box;direction:rtl;text-align:right;min-height:96px;padding:10px;margin-bottom:16px;border:1px solid #cbd5e1;border-radius:10px;font-family:Tahoma,Arial,sans-serif;font-size:13px;line-height:1.9;resize:vertical}" +
            "#" + config.overlayId + " .hint{font-size:12px;color:#64748b;margin:-10px 0 12px;line-height:1.6}" +
            "#" + config.overlayId + " .buttons{display:flex;gap:10px}" +
            "#" + config.overlayId + " button{flex:1;padding:12px;border:0;border-radius:10px;color:#fff;font-weight:700;cursor:pointer}" +
            "#" + config.overlayId + " .ack{background:#15803d}#" + config.overlayId + " .unack{background:#b91c1c}" +
            "#" + config.overlayId + " .close{display:block;width:100%;margin-top:12px;background:#b91c1c}" +
            ".ackToast{position:fixed;top:18px;left:50%;transform:translateX(-50%);z-index:2147483646;direction:rtl;display:flex;align-items:center;gap:10px;padding:12px 18px;border-radius:12px;background:#0f766e;color:#fff;font:600 13px/1.5 'Segoe UI',Tahoma,Arial,sans-serif;box-shadow:0 12px 30px rgba(0,0,0,.28);animation:ackIn .25s ease-out}" +
            ".ackToast.err{background:#b91c1c}" +
            ".ackLedger{font-family:'Segoe UI',Tahoma,Arial,sans-serif!important;font-size:13px!important;line-height:1.95!important;white-space:pre-wrap!important;overflow:auto;direction:rtl;text-align:right;background:#f6f8fa!important;color:#1f2937!important;border:1px solid #d7dee6!important;border-right:3px solid #2f6f8f!important;border-radius:4px;padding:10px 12px!important;min-height:230px!important;resize:none!important;cursor:default!important;caret-color:transparent}" +
            ".ackLedger:focus{outline:none!important;box-shadow:none!important}" +
            ".ackProtected{background:#f1f3f5!important;color:#6b7280!important;border:1px solid #dfe3e8!important;cursor:not-allowed!important;caret-color:transparent}" +
            ".ackProtected:focus{outline:none!important;box-shadow:none!important}";
        doc.head.appendChild(style);
    }

    function render(html) {
        var doc = parentWindow.document;
        ensureStyles();
        var overlay = doc.getElementById(config.overlayId) || doc.createElement("div");
        overlay.id = config.overlayId;
        overlay.innerHTML = html;
        if (!overlay.parentNode) doc.body.appendChild(overlay);
        return overlay;
    }

    function removeOverlay() {
        var overlay = parentWindow.document.getElementById(config.overlayId);
        if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
    }

    function toast(message, isError) {
        var doc = parentWindow.document;
        ensureStyles();
        var node = doc.createElement("div");
        node.className = "ackToast" + (isError ? " err" : "");
        node.innerHTML = "<span>" + (isError ? "✕" : "✔") + "</span><span>" + escapeHtml(message) + "</span>";
        doc.body.appendChild(node);
        parentWindow.setTimeout(function () {
            if (node.parentNode) node.parentNode.removeChild(node);
        }, config.toastMs);
    }

    /* يوحّد اسم الحقل: يتجاهل ة/ه والهمزات وتعدد المسافات */
    function fieldKey(value) {
        return normalize(value)
            .replace(/\s+/g, " ")
            .replace(/ة/g, "ه")
            .replace(/[أإآ]/g, "ا")
            .toLowerCase();
    }

    function labelContains(label, fieldName) {
        return fieldKey(label).indexOf(fieldKey(fieldName)) !== -1;
    }

    /* هل يملك المستخدم الحالي حق تعديل الحقول المحمية؟ */
    var canEditFields = null;
    function userCanEditFields() {
        if (canEditFields === null) {
            canEditFields = containsUser(config.fieldEditors, getCurrentUserName());
        }
        return canEditFields;
    }

    /** يجعل عنصر إدخال للعرض فقط. */
    function makeReadOnly(el, className, tooltip) {
        ensureStyles();
        el.setAttribute("data-ack-locked", "1");
        el.classList.add(className);
        el.readOnly = true;
        el.setAttribute("readonly", "readonly");
        el.setAttribute("aria-readonly", "true");
        el.title = tooltip;
        ["keydown", "keypress", "paste", "cut", "drop"].forEach(function (evt) {
            el.addEventListener(evt, function (e) { e.preventDefault(); e.stopPropagation(); }, true);
        });
    }

    /**
     * يقفل:
     *   - حقل السجل: للجميع دائمًا (يكتبه النظام تلقائيًا)
     *   - الحقول المحمية: لكل من ليس في fieldEditors
     */
    function lockStatusFieldUi() {
        if (!config.lockStatusField) return;

        var doc = parentWindow.document;
        var restricted = !userCanEditFields();
        var candidates = doc.querySelectorAll("textarea, input[type='text'], select");

        for (var i = 0; i < candidates.length; i++) {
            var el = candidates[i];
            if (el.getAttribute("data-ack-locked")) continue;

            var label = "";
            var scope = el.closest ? el.closest("[class*='field'], tr, li, div") : null;
            if (scope) {
                var lb = scope.querySelector("label, [class*='fieldName'], [class*='field-label']");
                label = normalize(lb && (lb.textContent || lb.innerText));
            }
            if (!label) label = normalize(el.getAttribute("aria-label") || el.getAttribute("title") || el.name);
            if (!label) continue;

            /* حقل السجل - مقفول للجميع */
            if (labelContains(label, config.statusField)) {
                makeReadOnly(el, "ackLedger", "سجل تلقائي — غير قابل للتعديل");
                continue;
            }

            if (!restricted) continue;

            /* الحقول المحمية - مقفولة لغير المخوَّلين */
            for (var f = 0; f < config.protectedFields.length; f++) {
                if (!labelContains(label, config.protectedFields[f])) continue;

                if (el.tagName === "SELECT") {
                    ensureStyles();
                    el.setAttribute("data-ack-locked", "1");
                    el.classList.add("ackProtected");
                    el.disabled = true;
                    el.title = "للعرض فقط";
                } else {
                    makeReadOnly(el, "ackProtected", "للعرض فقط");
                }
                break;
            }
        }
    }

    /* ================================================================== */
    /* تفعيل التتبع                                                        */
    /* ================================================================== */

    function managerButton() {
        return parentWindow.document.getElementById("customNewTrackingButton");
    }

    function endManagerFlow() {
        managerFlowActive = false;
        parentWindow.__newTrackRunningEntryId = null;
        var button = managerButton();
        if (button) button.classList.remove("ocr-running");
    }

    function showManagerResult(message, isError) {
        var overlay = render(
            '<div class="box"><div class="badge" style="background:' + (isError ? "#b91c1c" : "#15803d") + '">' + (isError ? "!" : "✓") + "</div>" +
            '<div class="title">' + (isError ? "حدث خطأ" : "تم بنجاح") + "</div>" +
            '<div class="msg">' + escapeHtml(message) + '</div><button class="close" data-action="close">إغلاق</button></div>'
        );
        overlay.querySelector('[data-action="close"]').onclick = function () {
            endManagerFlow();
            removeOverlay();
        };
    }

    function armTracking(context, recipients) {
        if (saving) return;
        saving = true;
        render('<div class="box"><div class="badge"><div class="spinner"></div></div><div class="title">جاري تفعيل التتبع</div><div class="msg">من فضلك انتظر لحظة...</div></div>');

        lock(context.entryId).then(function () {
            return readFields(context.entryId);
        }).then(function (fields) {
            if (!fields.status) throw new Error("الحقل غير موجود في القالب: " + config.statusField);
            var existing = parseLedger(fields.status.value || fields.status.Value || "");
            var state = {
                armed: true,
                sender: shortUser(context.userName),
                armedAt: stampNow(),
                done: existing.armed ? existing.done : [],
                pending: []
            };
            state = reconcile(state, recipients.map(shortUser));
            state.armed = true;
            state.sender = shortUser(context.userName);
            state.armedAt = stampNow();
            return save(context.entryId, fields.status.id, renderLedger(state));
        }).then(function () {
            return unlock(context.entryId);
        }).then(function () {
            saving = false;
            states = {};
            showManagerResult("تم تفعيل التتبع على " + recipients.length + " مستلمين.", false);
        }).catch(function (error) {
            saving = false;
            unlock(context.entryId);
            if (parentWindow.console) parentWindow.console.error("[NewTrack] Tracking failed.", error);
            showManagerResult("تعذر تفعيل التتبع.\n" + (error && error.message ? error.message : "خطأ غير متوقع"), true);
        });
    }

    parentWindow.runNewTrackingAction = function () {
        var entry = getFocusedEntry();
        var userName = getCurrentUserName();

        if (!entry) { parentWindow.alert("رجاء اختيار مستند واحد فقط"); return; }
        if (!containsUser(config.managerUsers, userName)) { parentWindow.alert("هذه الميزة متاحة للمُرسِل أو الأدمن فقط"); return; }
        if (entry.templateName && entry.templateName !== config.targetTemplate) {
            parentWindow.alert("هذا الزر متاح فقط على مستندات من نوع: " + config.targetTemplate);
            return;
        }
        if (parentWindow.__newTrackRunningEntryId === entry.id || saving || managerFlowActive) return;

        parentWindow.__newTrackRunningEntryId = entry.id;
        var button = managerButton();
        if (button) button.classList.add("ocr-running");
        managerFlowActive = true;

        var context = { entryId: entry.id, userName: userName, docName: entry.name || "" };

        readFields(context.entryId).then(function (fields) {
            if (!fields.status) throw new Error("الحقل غير موجود في القالب: " + config.statusField);

            /* الأسماء تأتي من حقل "المستلمون" الذي ملأه الـ Workflow */
            var preset = fieldToNames(fields.recipients);

            /* إن كان الحقل فارغًا، استخدم ما هو موجود في السجل الحالي */
            if (!preset.length) {
                var current = parseLedger(fields.status.value || fields.status.Value || "");
                preset = current.pending.concat(current.done.map(function (d) { return d.userName; }));
            }

            var warning = preset.length ? "" :
                '<div class="hint" style="color:#b91c1c">حقل «' + escapeHtml(config.recipientsField) + '» فارغ — تأكد أن الـ Workflow كتب الأسماء، أو أدخلها يدويًا.</div>';

            var overlay = render(
                '<div class="box"><div class="badge">✓</div><div class="title">تفعيل متابعة المستند</div>' +
                '<div class="msg">المستلمون كما قرأهم النظام — اسم في كل سطر' +
                (context.docName ? '<span class="doc">&quot;' + escapeHtml(context.docName) + '&quot;</span>' : "") + "</div>" +
                warning +
                '<textarea class="names" data-action="names" spellcheck="false">' + escapeHtml(preset.join("\n")) + "</textarea>" +
                '<div class="hint">سيبدأ الجميع بحالة «لم يتم الاطلاع»، ويُسجَّل كل مستخدم تلقائيًا بمجرد فتحه المستند.</div>' +
                '<div class="buttons"><button class="ack" data-action="start">بدء التتبع</button><button class="unack" data-action="cancel">إلغاء</button></div></div>'
            );

            var textarea = overlay.querySelector('[data-action="names"]');
            overlay.querySelector('[data-action="start"]').onclick = function () {
                var recipients = uniqueNames(splitNames(textarea.value));
                if (!recipients.length) { parentWindow.alert("أدخل اسم مستلم واحد على الأقل"); return; }
                armTracking(context, recipients);
            };
            overlay.querySelector('[data-action="cancel"]').onclick = function () {
                endManagerFlow();
                removeOverlay();
            };
        }).catch(function (error) {
            showManagerResult("تعذر قراءة بيانات المستند.\n" + (error && error.message ? error.message : ""), true);
        });
    };

    /* ================================================================== */
    /* التسجيل التلقائي                                                    */
    /* ================================================================== */

    function currentContext() {
        var entry = getFocusedEntry();
        var viewerId = getViewerEntryId();
        var entryId = viewerId || (entry && entry.id);
        var userName = getCurrentUserName();

        if (!entryId || userName === "Unknown" || containsUser(config.exemptUsers, userName)) return null;
        if (entry && viewerId && String(entry.id) !== String(viewerId)) return null;
        if (entry && entry.templateName && entry.templateName !== config.targetTemplate) return null;

        return {
            entryId: entryId,
            userName: userName,
            docName: (entry && entry.name) || "",
            scopeKey: String(entryId) + "_" + shortUser(userName).toLowerCase()
        };
    }

    function autoAcknowledge(context, state, fieldId) {
        if (saving) return;
        saving = true;

        var position = indexOfUser(state.pending, context.userName);
        var recordedName = state.pending[position];
        state.pending.splice(position, 1);
        state.done.push({ userName: recordedName, timestamp: stampNow() });

        var total = state.done.length + state.pending.length;

        lock(context.entryId).then(function () {
            return save(context.entryId, fieldId, renderLedger(state));
        }).then(function () {
            return unlock(context.entryId);
        }).then(function () {
            saving = false;
            var scope = states[context.scopeKey];
            if (scope) scope.resolved = true;
            toast("تم تسجيل اطلاعك — " + state.done.length + " " + L.of + " " + total, false);
        }).catch(function (error) {
            saving = false;
            unlock(context.entryId);
            var scope = states[context.scopeKey];
            if (scope) { scope.resolved = false; scope.checkedAt = Date.now(); }
            if (parentWindow.console) parentWindow.console.error("[NewTrack] Save failed.", error);
            toast("تعذر تسجيل الاطلاع، ستتم إعادة المحاولة.", true);
        });
    }

    function check() {
        if (parentWindow[config.ownerKey] !== instanceId) {
            if (intervalId) parentWindow.clearInterval(intervalId);
            return;
        }

        lockStatusFieldUi();
        if (managerFlowActive) return;

        var context = currentContext();
        if (!context) return;

        var state = states[context.scopeKey] || (states[context.scopeKey] = { checkedAt: 0, reading: false, resolved: false });
        if (state.reading || state.resolved || saving || Date.now() - state.checkedAt < config.throttleMs) return;

        state.checkedAt = Date.now();
        state.reading = true;

        readFields(context.entryId).then(function (fields) {
            state.reading = false;
            var latest = currentContext();
            if (!latest || latest.scopeKey !== context.scopeKey) return;
            if (!fields.status) { state.resolved = true; return; }

            var ledger = parseLedger(fields.status.value || fields.status.Value || "");

            /* التتبع غير مفعّل، أو المستخدم ليس مستلمًا، أو سجّل بالفعل */
            if (!ledger.armed || indexOfUser(ledger.pending, context.userName) === -1) {
                state.resolved = true;
                return;
            }

            autoAcknowledge(context, ledger, fields.status.id);
        }).catch(function (error) {
            state.reading = false;
            if (parentWindow.console) parentWindow.console.warn("[NewTrack] Metadata read failed.", error);
        });
    }

    parentWindow[config.ownerKey] = instanceId;
    if (parentWindow.console) {
        parentWindow.console.info("[NewTrack] ready | template: " + config.targetTemplate + " | ledger: " + config.statusField + " | recipients: " + config.recipientsField);
    }

    check();
    intervalId = parentWindow.setInterval(check, config.checkIntervalMs);

    window.addEventListener("unload", function () {
        if (intervalId) parentWindow.clearInterval(intervalId);
        if (parentWindow[config.ownerKey] === instanceId) parentWindow[config.ownerKey] = null;
    });

}());



// (function () {

//     "use strict";

//     /* =====================================================================
//      * New Tracking - Auto acknowledge, dynamic recipients, template: تتبع
//      * ---------------------------------------------------------------------
//      * مصدر أسماء المستلمين = حقل "المستلمون" الذي يملأه الـ Workflow.
//      * لا توجد أي أسماء ثابتة داخل الكود.
//      *
//      * التدفق:
//      *   1. الـ Workflow يكتب الأسماء في حقل "المستلمون".
//      *   2. المُرسِل يضغط زر Tracking  ->  يُبنى السجل في "تتبع حالة الملف".
//      *   3. كل مستلم يفتح المستند     ->  يُسجَّل اطلاعه تلقائيًا (مرة واحدة).
//      * ===================================================================== */

//     var config = {
//         targetTemplate: "تتبع",

//         /* الحقل الذي يكتب فيه الاسكريبت السجل - Text / 4000 */
//         statusField: "تتبع حالة الملف الحالي",

//         /* الحقل الذي يقرأ منه أسماء المستلمين - يملؤه الـ Workflow */
//         recipientsField: "المستلمون",

//         repoName: "Demo",

//         /* لا يُسجَّل لهم اطلاع تلقائي */
//         exemptUsers: ["ADMIN", "author", "workflow"],

//         /* من يملك زر Tracking */
//         managerUsers: ["ADMIN", "author"],

//         overlayId: "newTrackOverlay",
//         styleId: "newTrackOverlayStyles",
//         ownerKey: "__newTrackInstance",
//         checkIntervalMs: 400,
//         throttleMs: 800,
//         lockStatusField: true,
//         toastMs: 3500
//     };

//     var urls = {
//         metadata: "/laserfiche/MetadataService.ashx/GetMetadata",
//         lock: "/laserfiche/DocumentService.ashx/LockDocument",
//         unlock: "/laserfiche/DocumentService.ashx/UnlockDocument",
//         save: "/laserfiche/DocumentService.ashx/SaveEntry"
//     };

//     var L = {
//         title: "سجل الاطلاع على المستند",
//         sender: "المُرسِل",
//         status: "الحالة",
//         of: "من",
//         done: "تم الاطلاع",
//         pending: "لم يتم الاطلاع",
//         none: "لا يوجد حتى الآن",
//         all: "اكتمل اطلاع الجميع",
//         updated: "آخر تحديث",
//         rule: "──────────────────────────────────"
//     };

//     var LRM = "\u200E";
//     var BIDI_MARKS = /[\u200E\u200F\u202A-\u202E\u2066-\u2069]/g;

//     var parentWindow = window.parent || window;
//     var instanceId = Date.now() + "_" + Math.random().toString(36).slice(2);
//     var states = {};
//     var intervalId = null;
//     var saving = false;
//     var managerFlowActive = false;

//     /* ------------------------------------------------------------------ */
//     /* أدوات عامة                                                          */
//     /* ------------------------------------------------------------------ */

//     function normalize(value) {
//         return String(value || "").replace(BIDI_MARKS, "").trim();
//     }

//     function shortUser(value) {
//         return normalize(value).replace(/^.*[\\\/]/, "");
//     }

//     function sameUser(left, right) {
//         return shortUser(left).toLowerCase() === shortUser(right).toLowerCase();
//     }

//     function containsUser(users, userName) {
//         return users.some(function (item) { return sameUser(item, userName); });
//     }

//     function indexOfUser(users, userName) {
//         for (var i = 0; i < users.length; i++) {
//             if (sameUser(users[i], userName)) return i;
//         }
//         return -1;
//     }

//     function escapeHtml(value) {
//         return String(value || "").replace(/[&<>'"]/g, function (character) {
//             return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character];
//         });
//     }

//     function getLines(value) {
//         var text = String(value || "");
//         return text ? text.split(/\r?\n/) : [];
//     }

//     function splitNames(value) {
//         return String(value || "")
//             .split(/[;,،|\r\n]+/)
//             .map(normalize)
//             .filter(function (name) { return name.length > 0; });
//     }

//     function uniqueNames(names) {
//         var out = [];
//         names.forEach(function (name) {
//             if (indexOfUser(out, name) === -1) out.push(name);
//         });
//         return out;
//     }

//     function formatTimestamp(date) {
//         try {
//             return date.toLocaleString("ar-EG-u-nu-latn", {
//                 day: "2-digit", month: "2-digit", year: "numeric",
//                 hour: "2-digit", minute: "2-digit", hour12: true
//             });
//         } catch (ignore) {
//             return date.toLocaleString("en-US");
//         }
//     }

//     function stampNow() {
//         return normalize(formatTimestamp(new Date()));
//     }

//     function getCurrentUserName() {
//         var selector = '[lf-bind-once="loginInfo.DisplayUser"]';
//         try {
//             var boundElement = parentWindow.document.querySelector(selector);
//             if (boundElement && parentWindow.angular) {
//                 var scope = parentWindow.angular.element(boundElement).scope();
//                 for (var depth = 0; scope && depth < 8; depth++, scope = scope.$parent) {
//                     if (scope.loginInfo && scope.loginInfo.DisplayUser) {
//                         return normalize(scope.loginInfo.DisplayUser);
//                     }
//                 }
//             }
//             return normalize(boundElement && (boundElement.textContent || boundElement.innerText)) || "Unknown";
//         } catch (ignore) {
//             return "Unknown";
//         }
//     }

//     function getXsrfToken() {
//         var source = (window.parent && window.parent.document && window.parent !== window)
//             ? window.parent.document.cookie
//             : document.cookie;
//         var match = String(source || "").match(/(?:^|;\s*)XSRF-TOKEN=([^;]*)/);
//         return match ? decodeURIComponent(match[1]) : "";
//     }

//     function postJson(url, body) {
//         return parentWindow.fetch(url, {
//             method: "POST",
//             credentials: "same-origin",
//             headers: {
//                 "Content-Type": "application/json;charset=UTF-8",
//                 "Lf-Repository": config.repoName,
//                 "X-Lf-Repo-ID": config.repoName,
//                 "X-XSRF-TOKEN": getXsrfToken()
//             },
//             body: JSON.stringify(body)
//         }).then(function (response) {
//             if (!response.ok) throw new Error("HTTP " + response.status + " calling " + url);
//             return response.json();
//         });
//     }

//     function getFocusedEntry() {
//         try {
//             var api = parentWindow.webAccessApi || (typeof webAccessApi !== "undefined" && webAccessApi);
//             var entries = api && api.getFocusedEntries && api.getFocusedEntries();
//             return entries && entries.length === 1 ? entries[0] : null;
//         } catch (ignore) {
//             return null;
//         }
//     }

//     function getViewerEntryId() {
//         try {
//             var location = parentWindow.location;
//             var source = String(location.hash || "") + "&" + String(location.search || "") + "&" + String(location.href || "");
//             var match = source.match(/[?#&](?:id|entryId|docId|documentId)=(\d+)/i);
//             return match ? match[1] : null;
//         } catch (ignore) {
//             return null;
//         }
//     }

//     /* يقارن أسماء الحقول متجاهلًا الفرق بين ة/ه وتعدد المسافات */
//     function fieldNameMatches(actual, wanted) {
//         function key(value) {
//             return normalize(value).replace(/\s+/g, " ").replace(/ة/g, "ه").replace(/[أإآ]/g, "ا").toLowerCase();
//         }
//         return key(actual) === key(wanted);
//     }

//     /* يقرأ الحقلين معًا في نداء واحد */
//     function readFields(entryId) {
//         return postJson(urls.metadata, {
//             repoName: config.repoName,
//             entryIds: [String(entryId)],
//             metadataFlags: 1
//         }).then(function (result) {
//             var fields = result && result.d && result.d.Fields && result.d.Fields.templateFields;
//             if (!fields) throw new Error("Laserfiche did not return templateFields.");

//             var found = { status: null, recipients: null };
//             for (var i = 0; i < fields.length; i++) {
//                 if (fieldNameMatches(fields[i].name, config.statusField)) found.status = fields[i];
//                 else if (fieldNameMatches(fields[i].name, config.recipientsField)) found.recipients = fields[i];
//             }
//             return found;
//         });
//     }

//     /* يتعامل مع الحقل سواء كان قيمة واحدة أو متعدد القيم */
//     function fieldToNames(field) {
//         if (!field) return [];
//         var raw = field.values || field.Values;
//         if (raw && raw.length) {
//             var flat = [];
//             for (var i = 0; i < raw.length; i++) {
//                 var item = raw[i];
//                 flat = flat.concat(splitNames(item && item.value !== undefined ? item.value : item));
//             }
//             return uniqueNames(flat);
//         }
//         return uniqueNames(splitNames(field.value || field.Value || ""));
//     }

//     function lock(entryId) {
//         return postJson(urls.lock, { repoName: config.repoName, documentId: entryId, lockEfile: false, autoCheckout: false });
//     }

//     function unlock(entryId) {
//         return postJson(urls.unlock, { repoName: config.repoName, documentId: entryId }).catch(function (error) {
//             if (parentWindow.console) parentWindow.console.warn("[NewTrack] Unlock failed.", error);
//         });
//     }

//     function save(entryId, fieldId, value) {
//         return postJson(urls.save, {
//             repoName: config.repoName,
//             documentId: entryId,
//             curPageNum: 0,
//             strCurPageId: 0,
//             changes: {
//                 dirty: true, newTemplateId: 0, removeTemplate: false,
//                 fieldChanges: [{ fieldId: fieldId, value: value, remove: false, fieldIndex: 0 }],
//                 tagChanges: [], linkChanges: []
//             },
//             generalchanges: [],
//             annchanges: []
//         });
//     }

//     /* ================================================================== */
//     /* السجل                                                              */
//     /* ================================================================== */

//     function parseLedger(value) {
//         var state = { armed: false, sender: "", armedAt: "", done: [], pending: [] };
//         var lines = getLines(value);

//         for (var i = 0; i < lines.length; i++) {
//             var line = normalize(lines[i]);
//             if (!line) continue;
//             var m;

//             m = line.match(/^(?:المُرسِل|المرسل)\s*:\s*(.+?)\s+—\s+(.+?)$/);
//             if (m) { state.armed = true; state.sender = normalize(m[1]); state.armedAt = normalize(m[2]); continue; }

//             m = line.match(/^✔\s*(.+?)\s+—\s+(.+?)$/);
//             if (m) { state.done.push({ userName: normalize(m[1]), timestamp: normalize(m[2]) }); continue; }

//             m = line.match(/^✖\s*(.+?)$/);
//             if (m) { state.pending.push(normalize(m[1])); continue; }
//         }
//         return state;
//     }

//     function renderLedger(state) {
//         var total = state.done.length + state.pending.length;
//         var lines = [];

//         lines.push(L.title);
//         lines.push(L.sender + ": " + state.sender + " — " + LRM + state.armedAt + LRM);
//         lines.push(L.status + ": " + LRM + state.done.length + " " + L.of + " " + total + LRM);
//         lines.push(L.rule);

//         lines.push(L.done + " (" + state.done.length + ")");
//         if (state.done.length) {
//             state.done.forEach(function (item) {
//                 lines.push("✔ " + item.userName + " — " + LRM + item.timestamp + LRM);
//             });
//         } else {
//             lines.push("· " + L.none);
//         }

//         lines.push("");
//         lines.push(L.pending + " (" + state.pending.length + ")");
//         if (state.pending.length) {
//             state.pending.forEach(function (name) { lines.push("✖ " + name); });
//         } else {
//             lines.push("· " + L.all);
//         }

//         lines.push(L.rule);
//         lines.push(L.updated + ": " + LRM + stampNow() + LRM);
//         return lines.join("\n");
//     }

//     /**
//      * يوفّق السجل مع قائمة المستلمين الحالية:
//      * - من أُضيف في الحقل ولم يكن في السجل  -> يُضاف كـ "لم يتم الاطلاع"
//      * - من حُذف من الحقل                    -> يُزال من السجل
//      * يحافظ على أوقات من اطّلعوا بالفعل.
//      */
//     function reconcile(ledger, recipients) {
//         var done = ledger.done.filter(function (item) { return indexOfUser(recipients, item.userName) !== -1; });
//         var pending = [];
//         recipients.forEach(function (name) {
//             var already = done.some(function (item) { return sameUser(item.userName, name); });
//             if (!already) pending.push(name);
//         });
//         return { armed: ledger.armed, sender: ledger.sender, armedAt: ledger.armedAt, done: done, pending: pending };
//     }

//     /* ================================================================== */
//     /* واجهة                                                              */
//     /* ================================================================== */

//     function ensureStyles() {
//         var doc = parentWindow.document;
//         if (doc.getElementById(config.styleId)) return;
//         var style = doc.createElement("style");
//         style.id = config.styleId;
//         style.textContent =
//             "@keyframes ackSpin{to{transform:rotate(360deg)}}" +
//             "@keyframes ackIn{from{opacity:0;transform:translateY(-10px)}to{opacity:1;transform:none}}" +
//             "#" + config.overlayId + "{position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;justify-content:center;background:rgba(2,6,23,.9);backdrop-filter:blur(6px);font-family:'Segoe UI',Tahoma,Arial,sans-serif}" +
//             "#" + config.overlayId + " .box{direction:rtl;width:min(420px,calc(100vw - 48px));padding:32px;background:#fff;border-radius:16px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.45)}" +
//             "#" + config.overlayId + " .badge{display:flex;align-items:center;justify-content:center;width:52px;height:52px;margin:0 auto 16px;border-radius:50%;color:#fff;background:#2563eb;font-size:24px}" +
//             "#" + config.overlayId + " .spinner{width:22px;height:22px;border:3px solid rgba(255,255,255,.35);border-top-color:#fff;border-radius:50%;animation:ackSpin .8s linear infinite}" +
//             "#" + config.overlayId + " .title{font-size:18px;font-weight:700;color:#0f172a}" +
//             "#" + config.overlayId + " .msg{margin:8px 0 16px;white-space:pre-line;line-height:1.7;color:#475569}" +
//             "#" + config.overlayId + " .doc{display:block;color:#1e40af;font-weight:700;margin-top:4px}" +
//             "#" + config.overlayId + " .names{width:100%;box-sizing:border-box;direction:rtl;text-align:right;min-height:96px;padding:10px;margin-bottom:16px;border:1px solid #cbd5e1;border-radius:10px;font-family:Tahoma,Arial,sans-serif;font-size:13px;line-height:1.9;resize:vertical}" +
//             "#" + config.overlayId + " .hint{font-size:12px;color:#64748b;margin:-10px 0 12px;line-height:1.6}" +
//             "#" + config.overlayId + " .buttons{display:flex;gap:10px}" +
//             "#" + config.overlayId + " button{flex:1;padding:12px;border:0;border-radius:10px;color:#fff;font-weight:700;cursor:pointer}" +
//             "#" + config.overlayId + " .ack{background:#15803d}#" + config.overlayId + " .unack{background:#b91c1c}" +
//             "#" + config.overlayId + " .close{display:block;width:100%;margin-top:12px;background:#b91c1c}" +
//             ".ackToast{position:fixed;top:18px;left:50%;transform:translateX(-50%);z-index:2147483646;direction:rtl;display:flex;align-items:center;gap:10px;padding:12px 18px;border-radius:12px;background:#0f766e;color:#fff;font:600 13px/1.5 'Segoe UI',Tahoma,Arial,sans-serif;box-shadow:0 12px 30px rgba(0,0,0,.28);animation:ackIn .25s ease-out}" +
//             ".ackToast.err{background:#b91c1c}" +
//             ".ackLedger{font-family:'Segoe UI',Tahoma,Arial,sans-serif!important;font-size:13px!important;line-height:1.95!important;white-space:pre-wrap!important;overflow:auto;direction:rtl;text-align:right;background:#f6f8fa!important;color:#1f2937!important;border:1px solid #d7dee6!important;border-right:3px solid #2f6f8f!important;border-radius:4px;padding:10px 12px!important;min-height:230px!important;resize:none!important;cursor:default!important;caret-color:transparent}" +
//             ".ackLedger:focus{outline:none!important;box-shadow:none!important}";
//         doc.head.appendChild(style);
//     }

//     function render(html) {
//         var doc = parentWindow.document;
//         ensureStyles();
//         var overlay = doc.getElementById(config.overlayId) || doc.createElement("div");
//         overlay.id = config.overlayId;
//         overlay.innerHTML = html;
//         if (!overlay.parentNode) doc.body.appendChild(overlay);
//         return overlay;
//     }

//     function removeOverlay() {
//         var overlay = parentWindow.document.getElementById(config.overlayId);
//         if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
//     }

//     function toast(message, isError) {
//         var doc = parentWindow.document;
//         ensureStyles();
//         var node = doc.createElement("div");
//         node.className = "ackToast" + (isError ? " err" : "");
//         node.innerHTML = "<span>" + (isError ? "✕" : "✔") + "</span><span>" + escapeHtml(message) + "</span>";
//         doc.body.appendChild(node);
//         parentWindow.setTimeout(function () {
//             if (node.parentNode) node.parentNode.removeChild(node);
//         }, config.toastMs);
//     }

//     /* يطابق اسم الحقل في الواجهة مع تجاهل ة/ه والهمزات وتعدد المسافات */
//     function labelMatchesStatusField(label) {
//         function key(value) {
//             return normalize(value)
//                 .replace(/\s+/g, " ")
//                 .replace(/ة/g, "ه")
//                 .replace(/[أإآ]/g, "ا")
//                 .toLowerCase();
//         }
//         return key(label).indexOf(key(config.statusField)) !== -1;
//     }

//     function lockStatusFieldUi() {
//         if (!config.lockStatusField) return;
//         var doc = parentWindow.document;
//         var candidates = doc.querySelectorAll("textarea, input[type='text']");

//         for (var i = 0; i < candidates.length; i++) {
//             var el = candidates[i];
//             if (el.getAttribute("data-ack-locked")) continue;

//             var label = "";
//             var scope = el.closest ? el.closest("[class*='field'], tr, li, div") : null;
//             if (scope) {
//                 var lb = scope.querySelector("label, [class*='fieldName'], [class*='field-label']");
//                 label = normalize(lb && (lb.textContent || lb.innerText));
//             }
//             if (!label) label = normalize(el.getAttribute("aria-label") || el.getAttribute("title") || el.name);
//             if (!label || !labelMatchesStatusField(label)) continue;

//             ensureStyles();
//             el.setAttribute("data-ack-locked", "1");
//             el.classList.add("ackLedger");
//             el.readOnly = true;
//             el.setAttribute("readonly", "readonly");
//             el.setAttribute("aria-readonly", "true");
//             el.title = "سجل تلقائي — غير قابل للتعديل";
//             ["keydown", "keypress", "paste", "cut", "drop"].forEach(function (evt) {
//                 el.addEventListener(evt, function (e) { e.preventDefault(); e.stopPropagation(); }, true);
//             });
//         }
//     }

//     /* ================================================================== */
//     /* تفعيل التتبع                                                        */
//     /* ================================================================== */

//     function managerButton() {
//         return parentWindow.document.getElementById("customNewTrackingButton");
//     }

//     function endManagerFlow() {
//         managerFlowActive = false;
//         parentWindow.__newTrackRunningEntryId = null;
//         var button = managerButton();
//         if (button) button.classList.remove("ocr-running");
//     }

//     function showManagerResult(message, isError) {
//         var overlay = render(
//             '<div class="box"><div class="badge" style="background:' + (isError ? "#b91c1c" : "#15803d") + '">' + (isError ? "!" : "✓") + "</div>" +
//             '<div class="title">' + (isError ? "حدث خطأ" : "تم بنجاح") + "</div>" +
//             '<div class="msg">' + escapeHtml(message) + '</div><button class="close" data-action="close">إغلاق</button></div>'
//         );
//         overlay.querySelector('[data-action="close"]').onclick = function () {
//             endManagerFlow();
//             removeOverlay();
//         };
//     }

//     function armTracking(context, recipients) {
//         if (saving) return;
//         saving = true;
//         render('<div class="box"><div class="badge"><div class="spinner"></div></div><div class="title">جاري تفعيل التتبع</div><div class="msg">من فضلك انتظر لحظة...</div></div>');

//         lock(context.entryId).then(function () {
//             return readFields(context.entryId);
//         }).then(function (fields) {
//             if (!fields.status) throw new Error("الحقل غير موجود في القالب: " + config.statusField);
//             var existing = parseLedger(fields.status.value || fields.status.Value || "");
//             var state = {
//                 armed: true,
//                 sender: shortUser(context.userName),
//                 armedAt: stampNow(),
//                 done: existing.armed ? existing.done : [],
//                 pending: []
//             };
//             state = reconcile(state, recipients.map(shortUser));
//             state.armed = true;
//             state.sender = shortUser(context.userName);
//             state.armedAt = stampNow();
//             return save(context.entryId, fields.status.id, renderLedger(state));
//         }).then(function () {
//             return unlock(context.entryId);
//         }).then(function () {
//             saving = false;
//             states = {};
//             showManagerResult("تم تفعيل التتبع على " + recipients.length + " مستلمين.", false);
//         }).catch(function (error) {
//             saving = false;
//             unlock(context.entryId);
//             if (parentWindow.console) parentWindow.console.error("[NewTrack] Tracking failed.", error);
//             showManagerResult("تعذر تفعيل التتبع.\n" + (error && error.message ? error.message : "خطأ غير متوقع"), true);
//         });
//     }

//     parentWindow.runNewTrackingAction = function () {
//         var entry = getFocusedEntry();
//         var userName = getCurrentUserName();

//         if (!entry) { parentWindow.alert("رجاء اختيار مستند واحد فقط"); return; }
//         if (!containsUser(config.managerUsers, userName)) { parentWindow.alert("هذه الميزة متاحة للمُرسِل أو الأدمن فقط"); return; }
//         if (entry.templateName && entry.templateName !== config.targetTemplate) {
//             parentWindow.alert("هذا الزر متاح فقط على مستندات من نوع: " + config.targetTemplate);
//             return;
//         }
//         if (parentWindow.__newTrackRunningEntryId === entry.id || saving || managerFlowActive) return;

//         parentWindow.__newTrackRunningEntryId = entry.id;
//         var button = managerButton();
//         if (button) button.classList.add("ocr-running");
//         managerFlowActive = true;

//         var context = { entryId: entry.id, userName: userName, docName: entry.name || "" };

//         readFields(context.entryId).then(function (fields) {
//             if (!fields.status) throw new Error("الحقل غير موجود في القالب: " + config.statusField);

//             /* الأسماء تأتي من حقل "المستلمون" الذي ملأه الـ Workflow */
//             var preset = fieldToNames(fields.recipients);

//             /* إن كان الحقل فارغًا، استخدم ما هو موجود في السجل الحالي */
//             if (!preset.length) {
//                 var current = parseLedger(fields.status.value || fields.status.Value || "");
//                 preset = current.pending.concat(current.done.map(function (d) { return d.userName; }));
//             }

//             var warning = preset.length ? "" :
//                 '<div class="hint" style="color:#b91c1c">حقل «' + escapeHtml(config.recipientsField) + '» فارغ — تأكد أن الـ Workflow كتب الأسماء، أو أدخلها يدويًا.</div>';

//             var overlay = render(
//                 '<div class="box"><div class="badge">✓</div><div class="title">تفعيل متابعة المستند</div>' +
//                 '<div class="msg">المستلمون كما قرأهم النظام — اسم في كل سطر' +
//                 (context.docName ? '<span class="doc">&quot;' + escapeHtml(context.docName) + '&quot;</span>' : "") + "</div>" +
//                 warning +
//                 '<textarea class="names" data-action="names" spellcheck="false">' + escapeHtml(preset.join("\n")) + "</textarea>" +
//                 '<div class="hint">سيبدأ الجميع بحالة «لم يتم الاطلاع»، ويُسجَّل كل مستخدم تلقائيًا بمجرد فتحه المستند.</div>' +
//                 '<div class="buttons"><button class="ack" data-action="start">بدء التتبع</button><button class="unack" data-action="cancel">إلغاء</button></div></div>'
//             );

//             var textarea = overlay.querySelector('[data-action="names"]');
//             overlay.querySelector('[data-action="start"]').onclick = function () {
//                 var recipients = uniqueNames(splitNames(textarea.value));
//                 if (!recipients.length) { parentWindow.alert("أدخل اسم مستلم واحد على الأقل"); return; }
//                 armTracking(context, recipients);
//             };
//             overlay.querySelector('[data-action="cancel"]').onclick = function () {
//                 endManagerFlow();
//                 removeOverlay();
//             };
//         }).catch(function (error) {
//             showManagerResult("تعذر قراءة بيانات المستند.\n" + (error && error.message ? error.message : ""), true);
//         });
//     };

//     /* ================================================================== */
//     /* التسجيل التلقائي                                                    */
//     /* ================================================================== */

//     function currentContext() {
//         var entry = getFocusedEntry();
//         var viewerId = getViewerEntryId();
//         var entryId = viewerId || (entry && entry.id);
//         var userName = getCurrentUserName();

//         if (!entryId || userName === "Unknown" || containsUser(config.exemptUsers, userName)) return null;
//         if (entry && viewerId && String(entry.id) !== String(viewerId)) return null;
//         if (entry && entry.templateName && entry.templateName !== config.targetTemplate) return null;

//         return {
//             entryId: entryId,
//             userName: userName,
//             docName: (entry && entry.name) || "",
//             scopeKey: String(entryId) + "_" + shortUser(userName).toLowerCase()
//         };
//     }

//     function autoAcknowledge(context, state, fieldId) {
//         if (saving) return;
//         saving = true;

//         var position = indexOfUser(state.pending, context.userName);
//         var recordedName = state.pending[position];
//         state.pending.splice(position, 1);
//         state.done.push({ userName: recordedName, timestamp: stampNow() });

//         var total = state.done.length + state.pending.length;

//         lock(context.entryId).then(function () {
//             return save(context.entryId, fieldId, renderLedger(state));
//         }).then(function () {
//             return unlock(context.entryId);
//         }).then(function () {
//             saving = false;
//             var scope = states[context.scopeKey];
//             if (scope) scope.resolved = true;
//             toast("تم تسجيل اطلاعك — " + state.done.length + " " + L.of + " " + total, false);
//         }).catch(function (error) {
//             saving = false;
//             unlock(context.entryId);
//             var scope = states[context.scopeKey];
//             if (scope) { scope.resolved = false; scope.checkedAt = Date.now(); }
//             if (parentWindow.console) parentWindow.console.error("[NewTrack] Save failed.", error);
//             toast("تعذر تسجيل الاطلاع، ستتم إعادة المحاولة.", true);
//         });
//     }

//     function check() {
//         if (parentWindow[config.ownerKey] !== instanceId) {
//             if (intervalId) parentWindow.clearInterval(intervalId);
//             return;
//         }

//         lockStatusFieldUi();
//         if (managerFlowActive) return;

//         var context = currentContext();
//         if (!context) return;

//         var state = states[context.scopeKey] || (states[context.scopeKey] = { checkedAt: 0, reading: false, resolved: false });
//         if (state.reading || state.resolved || saving || Date.now() - state.checkedAt < config.throttleMs) return;

//         state.checkedAt = Date.now();
//         state.reading = true;

//         readFields(context.entryId).then(function (fields) {
//             state.reading = false;
//             var latest = currentContext();
//             if (!latest || latest.scopeKey !== context.scopeKey) return;
//             if (!fields.status) { state.resolved = true; return; }

//             var ledger = parseLedger(fields.status.value || fields.status.Value || "");

//             /* التتبع غير مفعّل، أو المستخدم ليس مستلمًا، أو سجّل بالفعل */
//             if (!ledger.armed || indexOfUser(ledger.pending, context.userName) === -1) {
//                 state.resolved = true;
//                 return;
//             }

//             autoAcknowledge(context, ledger, fields.status.id);
//         }).catch(function (error) {
//             state.reading = false;
//             if (parentWindow.console) parentWindow.console.warn("[NewTrack] Metadata read failed.", error);
//         });
//     }

//     parentWindow[config.ownerKey] = instanceId;
//     if (parentWindow.console) {
//         parentWindow.console.info("[NewTrack] ready | template: " + config.targetTemplate + " | ledger: " + config.statusField + " | recipients: " + config.recipientsField);
//     }

//     check();
//     intervalId = parentWindow.setInterval(check, config.checkIntervalMs);

//     window.addEventListener("unload", function () {
//         if (intervalId) parentWindow.clearInterval(intervalId);
//         if (parentWindow[config.ownerKey] === instanceId) parentWindow[config.ownerKey] = null;
//     });

// }());

