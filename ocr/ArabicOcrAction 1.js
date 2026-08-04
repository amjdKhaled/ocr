// // // // // window.runArabicOcrAction = function () {

// // // // //     var OVERLAY_ID = "arabicOcrOverlay";
// // // // //     var BTN_ID = "customOcrButton";
// // // // //     var repoName = new URLSearchParams(window.location.search).get("repo") || "demo";
// // // // //     // var OCR_SERVICE_URL = "http://localhost:8001";
// // // // //     var OCR_SERVICE_URL = window.location.protocol + "//" + window.location.hostname + ":8001";
// // // // //     var documentWasLocked = false;
// // // // //     var entryId = null;

// // // // //     // ---------- Overlay UI ----------
// // // // //     function ensureOverlayStyles() {
// // // // //         if (document.getElementById("arabicOcrOverlayStyles")) return;
// // // // //         var style = document.createElement("style");
// // // // //         style.id = "arabicOcrOverlayStyles";
// // // // //         style.innerHTML =
// // // // //             "#" + OVERLAY_ID + "{position:fixed;top:0;left:0;width:100%;height:100%;" +
// // // // //             "background:rgba(0,0,0,0.55);z-index:2147483647;display:flex;" +
// // // // //             "align-items:center;justify-content:center;font-family:Tahoma,Arial,sans-serif;}" +
// // // // //             "#" + OVERLAY_ID + " .aoBox{background:#fff;border-radius:10px;padding:28px 32px;" +
// // // // //             "min-width:280px;max-width:420px;text-align:center;box-shadow:0 6px 24px rgba(0,0,0,0.3);direction:rtl;}" +
// // // // //             "#" + OVERLAY_ID + " .aoSpinner{width:42px;height:42px;margin:0 auto 16px;" +
// // // // //             "border:4px solid #ddd;border-top-color:#2b6cb0;border-radius:50%;" +
// // // // //             "animation:aoSpin 0.9s linear infinite;}" +
// // // // //             "@keyframes aoSpin{to{transform:rotate(360deg);}}" +
// // // // //             "#" + OVERLAY_ID + " .aoMsg{font-size:15px;color:#222;margin-bottom:4px;white-space:pre-line;}" +
// // // // //             "#" + OVERLAY_ID + " .aoIcon{font-size:38px;margin-bottom:10px;}" +
// // // // //             "#" + OVERLAY_ID + " .aoClose{margin-top:16px;padding:8px 22px;border:none;" +
// // // // //             "border-radius:6px;background:#2b6cb0;color:#fff;font-size:14px;cursor:pointer;}" +
// // // // //             "#" + OVERLAY_ID + " .aoClose.error{background:#c53030;}";
// // // // //         document.head.appendChild(style);
// // // // //     }

// // // // //     function getOverlayEl() {
// // // // //         var overlay = document.getElementById(OVERLAY_ID);
// // // // //         if (!overlay) {
// // // // //             overlay = document.createElement("div");
// // // // //             overlay.id = OVERLAY_ID;
// // // // //             document.body.appendChild(overlay);
// // // // //         }
// // // // //         return overlay;
// // // // //     }

// // // // //     function showOverlayLoading(message) {
// // // // //         ensureOverlayStyles();
// // // // //         var overlay = getOverlayEl();
// // // // //         overlay.innerHTML =
// // // // //             '<div class="aoBox"><div class="aoSpinner"></div><div class="aoMsg">' +
// // // // //             message + "</div></div>";
// // // // //     }

// // // // //     function showOverlayResult(message, isError) {
// // // // //         ensureOverlayStyles();
// // // // //         var overlay = getOverlayEl();
// // // // //         var icon = isError ? "\u26A0\uFE0F" : "\u2705";
// // // // //         overlay.innerHTML =
// // // // //             '<div class="aoBox"><div class="aoIcon">' + icon + '</div><div class="aoMsg">' +
// // // // //             message + '</div><button class="aoClose' + (isError ? " error" : "") +
// // // // //             '" id="aoCloseBtn">تم</button></div>';
// // // // //         document.getElementById("aoCloseBtn").onclick = function () {
// // // // //             hideOverlay();
// // // // //         };
// // // // //         unlockButton();
// // // // //     }

// // // // //     function hideOverlay() {
// // // // //         var overlay = document.getElementById(OVERLAY_ID);
// // // // //         if (overlay && overlay.parentNode) {
// // // // //             overlay.parentNode.removeChild(overlay);
// // // // //         }
// // // // //     }

// // // // //     // ---------- منع الضغط المزدوج (مربوط بالمستند الحالي فقط) ----------
// // // // //     var btn = document.getElementById(BTN_ID);

// // // // //     function unlockButton() {
// // // // //         window.__ocrRunningEntryId = null;
// // // // //         if (btn) btn.classList.remove("ocr-running");
// // // // //     }

// // // // //     // ---------- Helpers ----------
// // // // //     function getXsrfToken() {
// // // // //         var match = document.cookie.match(/(?:^|;\s*)XSRF-TOKEN=([^;]*)/);
// // // // //         return match ? decodeURIComponent(match[1]) : "";
// // // // //     }

// // // // //     function postJson(url, body) {
// // // // //         return fetch(url, {
// // // // //             method: "POST",
// // // // //             credentials: "same-origin",
// // // // //             headers: {
// // // // //                 "Content-Type": "application/json;charset=UTF-8",
// // // // //                 "Lf-Repository": repoName,
// // // // //                 "X-Lf-Repo-ID": repoName,
// // // // //                 "X-XSRF-TOKEN": getXsrfToken()
// // // // //             },
// // // // //             body: JSON.stringify(body)
// // // // //         }).then(function (r) {
// // // // //             if (!r.ok) {
// // // // //                 throw new Error("طلب الشبكة فشل (" + r.status + "): " + url);
// // // // //             }
// // // // //             return r.json();
// // // // //         });
// // // // //     }

// // // // //     function sleep(ms) {
// // // // //         return new Promise(function (resolve) { setTimeout(resolve, ms); });
// // // // //     }

// // // // //     function getCurrentPageId() {
// // // // //         try {
// // // // //             var resources = performance.getEntriesByType("resource");
// // // // //             for (var i = resources.length - 1; i >= 0; i--) {
// // // // //                 var url = resources[i].name;
// // // // //                 if (url.indexOf("TileData.aspx") !== -1 &&
// // // // //                     url.indexOf("documentId=" + entryId) !== -1) {
// // // // //                     var m = url.match(/[?&]pageId=([^&]+)/);
// // // // //                     if (m) return m[1];
// // // // //                 }
// // // // //             }
// // // // //         } catch (e) {
// // // // //             console.warn("ArabicOCR: تعذر قراءة pageId من resource timing - ", e);
// // // // //         }
// // // // //         return null;
// // // // //     }

// // // // //     function refreshSessionBeforeSave() {
// // // // //         return postJson("/laserfiche/MetadataService.ashx/GetMetadata", {
// // // // //             repoName: repoName,
// // // // //             entryIds: [String(entryId)],
// // // // //             metadataFlags: 1
// // // // //         }).catch(function (err) {
// // // // //             console.warn("ArabicOCR: فشل تجديد الجلسة قبل الحفظ - ", err);
// // // // //         });
// // // // //     }

// // // // //     function unlockDocument() {
// // // // //         if (!documentWasLocked) {
// // // // //             return Promise.resolve();
// // // // //         }
// // // // //         return postJson("/laserfiche/DocumentService.ashx/UnlockDocument", {
// // // // //             repoName: repoName,
// // // // //             documentId: entryId
// // // // //         }).then(function (result) {
// // // // //             documentWasLocked = false;
// // // // //             return result;
// // // // //         }).catch(function (err) {
// // // // //             console.warn("ArabicOCR: فشل فك القفل عن المستند - ", err);
// // // // //         });
// // // // //     }

// // // // //     function saveFullTextToTextPane(pageId, fullText) {
// // // // //         if (!pageId || !fullText) {
// // // // //             return Promise.resolve();
// // // // //         }
// // // // //         return postJson("/laserfiche/DocumentService.ashx/SetTextByDocIdAndPageId", {
// // // // //             repoName: repoName,
// // // // //             documentId: entryId,
// // // // //             strPageId: String(pageId),
// // // // //             newText: fullText,
// // // // //             hints: []
// // // // //         }).catch(function (err) {
// // // // //             console.warn("ArabicOCR: فشل حفظ النص الكامل في بانل Text - ", err);
// // // // //         });
// // // // //     }

// // // // //     function startExport() {
// // // // //         var url = "/laserfiche/Dialogs/Export/ExportDisplay.aspx"
// // // // //             + "?r=" + encodeURIComponent(repoName)
// // // // //             + "&t=1&i=" + entryId + "&v=0&p=1&f=3&optToken=&sh=&loc=0&sep=&reportFormat=&e=";
// // // // //         return fetch(url, { credentials: "same-origin" })
// // // // //             .then(function (r) {
// // // // //                 if (!r.ok) throw new Error("فشل بدء عملية التصدير (" + r.status + ")");
// // // // //                 return r.text();
// // // // //             })
// // // // //             .then(function (html) {
// // // // //                 var m = html.match(/exportToken&quot;:&quot;([a-f0-9-]+)&quot;/i)
// // // // //                       || html.match(/"exportToken"\s*:\s*"([a-f0-9-]+)"/i);
// // // // //                 if (!m) throw new Error("تعذر الحصول على exportToken");
// // // // //                 return m[1];
// // // // //             });
// // // // //     }

// // // // //     function waitForExport(token) {
// // // // //         var attempts = 0;
// // // // //         function check() {
// // // // //             attempts++;
// // // // //             if (attempts > 40) throw new Error("انتهت مهلة انتظار التصدير (Timeout)");
// // // // //             return postJson("/laserfiche/ExportService.ashx/GetExportStatus", {
// // // // //                 repoName: repoName,
// // // // //                 token: token
// // // // //             }).then(function (statusResult) {
// // // // //                 var s = statusResult.d;
// // // // //                 if (!s) throw new Error("استجابة غير متوقعة أثناء التصدير");
// // // // //                 if (s.State === 2 || s.Completion === 100) {
// // // // //                     return token;
// // // // //                 }
// // // // //                 if (s.FailMsg) throw new Error("فشل التصدير: " + s.FailMsg);
// // // // //                 return sleep(500).then(check);
// // // // //             });
// // // // //         }
// // // // //         return check();
// // // // //     }

// // // // //     function downloadExportedFile(token) {
// // // // //         var url = "/laserfiche/Dialogs/Export/GetExportFile.aspx?token="
// // // // //             + encodeURIComponent(token) + "&repo=" + encodeURIComponent(repoName);
// // // // //         return fetch(url, { credentials: "same-origin" })
// // // // //             .then(function (r) {
// // // // //                 if (!r.ok) throw new Error("فشل تحميل الملف المُصدَّر (" + r.status + ")");
// // // // //                 return r.blob();
// // // // //             });
// // // // //     }

// // // // //     function callOcrService(path, formData) {
// // // // //         return fetch(OCR_SERVICE_URL + path, {
// // // // //             method: "POST",
// // // // //             body: formData
// // // // //         }).then(function (r) {
// // // // //             if (!r.ok) {
// // // // //                 return r.text().then(function (t) {
// // // // //                     throw new Error("خدمة الـ OCR رفضت الطلب: " + (t || r.status));
// // // // //                 });
// // // // //             }
// // // // //             return r.json();
// // // // //         }).catch(function (err) {
// // // // //             if (err.message && err.message.indexOf("خدمة الـ OCR") === 0) {
// // // // //                 throw err;
// // // // //             }
// // // // //             throw new Error("تعذر الاتصال بخدمة الـ OCR المحلية (تأكد إن السيرفر شغال على " + OCR_SERVICE_URL + ")");
// // // // //         });
// // // // //     }

// // // // //     // ================= التنفيذ الفعلي =================

// // // // //     // --- تحقق من توفر webAccessApi ---
// // // // //     if (typeof webAccessApi === "undefined" || !webAccessApi.getFocusedEntries) {
// // // // //         alert("حدث خطأ: واجهة WebAccess غير متاحة في هذه الصفحة");
// // // // //         return;
// // // // //     }

// // // // //     // --- تحقق من اختيار مستند واحد بالظبط ---
// // // // //     var entries;
// // // // //     try {
// // // // //         entries = webAccessApi.getFocusedEntries();
// // // // //     } catch (e) {
// // // // //         alert("تعذر قراءة المستند المحدد");
// // // // //         return;
// // // // //     }

// // // // //     if (!entries || entries.length === 0) {
// // // // //         alert("رجاء اختيار مستند أولاً");
// // // // //         return;
// // // // //     }
// // // // //     if (entries.length > 1) {
// // // // //         alert("رجاء اختيار مستند واحد فقط");
// // // // //         return;
// // // // //     }

// // // // //     entryId = entries[0].id;

// // // // //     // --- منع الضغط المزدوج على *نفس المستند* فقط ---
// // // // //     if (window.__ocrRunningEntryId === entryId) {
// // // // //         return; // فيه عملية شغالة بالفعل على نفس المستند ده تحديدًا
// // // // //     }
// // // // //     window.__ocrRunningEntryId = entryId;
// // // // //     if (btn) btn.classList.add("ocr-running");

// // // // //     var fieldsById = {};
// // // // //     var pageIdForText = getCurrentPageId();

// // // // //     showOverlayLoading("جاري قراءة بيانات القالب...");

// // // // //     postJson("/laserfiche/MetadataService.ashx/GetMetadata", {
// // // // //         repoName: repoName,
// // // // //         entryIds: [String(entryId)],
// // // // //         metadataFlags: 1
// // // // //     })
// // // // //     .then(function (metaResult) {
// // // // //         if (!metaResult || !metaResult.d || !metaResult.d.Fields) {
// // // // //             throw new Error("لا يمكن قراءة حقول القالب لهذا المستند (تأكد إن له قالب)");
// // // // //         }
// // // // //         var fields = metaResult.d.Fields.templateFields || [];
// // // // //         fields.forEach(function (f) { fieldsById[f.name] = f.id; });

// // // // //         showOverlayLoading("جاري تصدير المستند...");
// // // // //         return startExport();
// // // // //     })
// // // // //     .then(function (token) {
// // // // //         showOverlayLoading("جاري تجهيز الصورة للتحليل...");
// // // // //         return waitForExport(token).then(downloadExportedFile);
// // // // //     })
// // // // //     .then(function (pdfBlob) {
// // // // //         if (!pdfBlob || pdfBlob.size === 0) {
// // // // //             throw new Error("الملف المُصدَّر فارغ، تعذر المتابعة");
// // // // //         }

// // // // //         showOverlayLoading("جاري تحليل المستند بالذكاء الاصطناعي...\nقد تستغرق العملية بعض الوقت، برجاء الانتظار.");

// // // // //         var fieldsFormData = new FormData();
// // // // //         fieldsFormData.append("image", pdfBlob, "page.pdf");
// // // // //         fieldsFormData.append("fields", Object.keys(fieldsById).join(","));

// // // // //         var allTextFormData = new FormData();
// // // // //         allTextFormData.append("image", pdfBlob, "page.pdf");

// // // // //         var extractFieldsPromise = callOcrService("/extract", fieldsFormData);

// // // // //         var extractAllTextPromise = callOcrService("/extract-all-text", allTextFormData)
// // // // //             .catch(function (err) {
// // // // //                 console.warn("ArabicOCR: فشل استخراج النص الكامل - ", err);
// // // // //                 return null;
// // // // //             });

// // // // //         return Promise.all([extractFieldsPromise, extractAllTextPromise]);
// // // // //     })
// // // // //     .then(function (results) {
// // // // //         var extracted = results[0] || {};
// // // // //         var allTextResult = results[1];

// // // // //         var fieldChanges = [];
// // // // //         Object.keys(extracted).forEach(function (name) {
// // // // //             if (fieldsById.hasOwnProperty(name) && extracted[name]) {
// // // // //                 fieldChanges.push({
// // // // //                     fieldId: fieldsById[name],
// // // // //                     value: String(extracted[name]).trim(),
// // // // //                     remove: false,
// // // // //                     fieldIndex: 0
// // // // //                 });
// // // // //             }
// // // // //         });

// // // // //         if (fieldChanges.length === 0 && !(allTextResult && allTextResult.text)) {
// // // // //             showOverlayResult("لم يتم التعرف على أي حقول أو نص في هذا المستند", true);
// // // // //             return null;
// // // // //         }

// // // // //         showOverlayLoading("جاري حفظ البيانات في المستند...");

// // // // //         return refreshSessionBeforeSave().then(function () {
// // // // //             return postJson("/laserfiche/DocumentService.ashx/LockDocument", {
// // // // //                 repoName: repoName,
// // // // //                 documentId: entryId,
// // // // //                 lockEfile: false,
// // // // //                 autoCheckout: false
// // // // //             });
// // // // //         }).then(function () {
// // // // //             documentWasLocked = true;
// // // // //             return saveFullTextToTextPane(
// // // // //                 pageIdForText,
// // // // //                 allTextResult ? allTextResult.text : null
// // // // //             );
// // // // //         }).then(function () {
// // // // //             if (fieldChanges.length === 0) {
// // // // //                 return unlockDocument().then(function () { return { d: true }; });
// // // // //             }
// // // // //             return postJson("/laserfiche/DocumentService.ashx/SaveEntry", {
// // // // //                 repoName: repoName,
// // // // //                 documentId: entryId,
// // // // //                 curPageNum: 0,
// // // // //                 strCurPageId: 0,
// // // // //                 changes: {
// // // // //                     dirty: true,
// // // // //                     newTemplateId: 0,
// // // // //                     removeTemplate: false,
// // // // //                     fieldChanges: fieldChanges,
// // // // //                     tagChanges: [],
// // // // //                     linkChanges: []
// // // // //                 },
// // // // //                 generalchanges: [],
// // // // //                 annchanges: []
// // // // //             }).then(function (saveResult) {
// // // // //                 return unlockDocument().then(function () {
// // // // //                     return saveResult;
// // // // //                 });
// // // // //             });
// // // // //         });
// // // // //     })
// // // // //     .then(function (saveResult) {
// // // // //         if (saveResult) {
// // // // //             try {
// // // // //                 webAccessApi.refreshMetadata();
// // // // //             } catch (e) {
// // // // //                 console.warn("ArabicOCR: فشل تحديث الميتاداتا في الواجهة - ", e);
// // // // //             }
// // // // //             try {
// // // // //                 // محاولة تحديث بانل المحتوى (قد يشمل Text Pane) - لا يوجد دالة
// // // // //                 // رسمية مخصصة لبانل النص في webAccessApi، فده أقرب محاولة.
// // // // //                 webAccessApi.refreshContentsPane();
// // // // //             } catch (e) {
// // // // //                 console.warn("ArabicOCR: فشل تحديث Contents Pane - ", e);
// // // // //             }
// // // // //             showOverlayResult("تم استخراج البيانات وحفظها بنجاح ✔");
// // // // //             // fallback مضمون: لو بانل الـ Text مبيتحدثش لايف (مفيش API رسمي
// // // // //             // له)، نعمل reload تلقائي للصفحة بعد ما المستخدم يشوف رسالة
// // // // //             // النجاح، عشان يظهر كل حاجة (Fields + Text) من غير أي تدخل يدوي.
// // // // //             setTimeout(function () {
// // // // //                 location.reload();
// // // // //             }, 1500);
// // // // //         }
// // // // //     })
// // // // //     .catch(function (err) {
// // // // //         console.error("ArabicOCR Error:", err);
// // // // //         unlockDocument().then(function () {
// // // // //             showOverlayResult("حدث خطأ:\n" + (err && err.message ? err.message : "خطأ غير متوقع"), true);
// // // // //         });
// // // // //     });
// // // // // };




// // // // window.runArabicOcrAction = function () {

// // // //     var OVERLAY_ID = "arabicOcrOverlay";
// // // //     var BTN_ID = "customOcrButton";
// // // //     var repoName = new URLSearchParams(window.location.search).get("repo") || "demo";
// // // //     var OCR_SERVICE_URL = window.location.protocol + "//" + window.location.hostname + ":8001";
// // // //     var documentWasLocked = false;
// // // //     var entryId = null;
// // // //     var textError = null;   // سبب فشل استخراج النص الكامل، لو حصل

// // // //     // ⚠⚠ مشكلة "أول صفحة بس" ⚠⚠
// // // //     // القيمة دي هي اللي بتحدد الصفحات اللي بتتصدّر. p=1 على الأغلب معناها
// // // //     // "الصفحة الحالية" مش "كل الصفحات".
// // // //     //
// // // //     // إزاي تتأكد في 30 ثانية: افتح مستند من 5 صفحات، اعمل Export من واجهة
// // // //     // Laserfiche نفسها، اختار "All pages"، وشوف قيمة p في الـ Network tab.
// // // //     // حط القيمة الصحيحة هنا وخلاص.
// // // //     var EXPORT_PAGES_PARAM = "1";

// // // //     // ---------- Overlay UI ----------
// // // //     function ensureOverlayStyles() {
// // // //         if (document.getElementById("arabicOcrOverlayStyles")) return;
// // // //         var style = document.createElement("style");
// // // //         style.id = "arabicOcrOverlayStyles";
// // // //         style.innerHTML =
// // // //             "#" + OVERLAY_ID + "{position:fixed;top:0;left:0;width:100%;height:100%;" +
// // // //             "background:rgba(0,0,0,0.55);z-index:2147483647;display:flex;" +
// // // //             "align-items:center;justify-content:center;font-family:Tahoma,Arial,sans-serif;}" +
// // // //             "#" + OVERLAY_ID + " .aoBox{background:#fff;border-radius:10px;padding:28px 32px;" +
// // // //             "min-width:280px;max-width:420px;text-align:center;box-shadow:0 6px 24px rgba(0,0,0,0.3);direction:rtl;}" +
// // // //             "#" + OVERLAY_ID + " .aoSpinner{width:42px;height:42px;margin:0 auto 16px;" +
// // // //             "border:4px solid #ddd;border-top-color:#2b6cb0;border-radius:50%;" +
// // // //             "animation:aoSpin 0.9s linear infinite;}" +
// // // //             "@keyframes aoSpin{to{transform:rotate(360deg);}}" +
// // // //             "#" + OVERLAY_ID + " .aoMsg{font-size:15px;color:#222;margin-bottom:4px;white-space:pre-line;}" +
// // // //             "#" + OVERLAY_ID + " .aoIcon{font-size:38px;margin-bottom:10px;}" +
// // // //             "#" + OVERLAY_ID + " .aoClose{margin-top:16px;padding:8px 22px;border:none;" +
// // // //             "border-radius:6px;background:#2b6cb0;color:#fff;font-size:14px;cursor:pointer;}" +
// // // //             "#" + OVERLAY_ID + " .aoClose.error{background:#c53030;}" +
// // // //             "#" + OVERLAY_ID + " .aoWarn{margin-top:10px;font-size:13px;color:#b7791f;" +
// // // //             "white-space:pre-line;direction:rtl;}";
// // // //         document.head.appendChild(style);
// // // //     }

// // // //     function getOverlayEl() {
// // // //         var overlay = document.getElementById(OVERLAY_ID);
// // // //         if (!overlay) {
// // // //             overlay = document.createElement("div");
// // // //             overlay.id = OVERLAY_ID;
// // // //             document.body.appendChild(overlay);
// // // //         }
// // // //         return overlay;
// // // //     }

// // // //     function showOverlayLoading(message) {
// // // //         ensureOverlayStyles();
// // // //         getOverlayEl().innerHTML =
// // // //             '<div class="aoBox"><div class="aoSpinner"></div><div class="aoMsg">' +
// // // //             message + "</div></div>";
// // // //     }

// // // //     function showOverlayResult(message, isError, warning) {
// // // //         ensureOverlayStyles();
// // // //         var overlay = getOverlayEl();
// // // //         var icon = isError ? "\u26A0\uFE0F" : "\u2705";
// // // //         overlay.innerHTML =
// // // //             '<div class="aoBox"><div class="aoIcon">' + icon + '</div><div class="aoMsg">' +
// // // //             message + '</div>' +
// // // //             (warning ? '<div class="aoWarn">' + warning + '</div>' : '') +
// // // //             '<button class="aoClose' + (isError ? " error" : "") +
// // // //             '" id="aoCloseBtn">تم</button></div>';
// // // //         document.getElementById("aoCloseBtn").onclick = hideOverlay;
// // // //         unlockButton();
// // // //     }

// // // //     function hideOverlay() {
// // // //         var overlay = document.getElementById(OVERLAY_ID);
// // // //         if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
// // // //     }

// // // //     // ---------- منع الضغط المزدوج (مربوط بالمستند الحالي فقط) ----------
// // // //     var btn = document.getElementById(BTN_ID);

// // // //     function unlockButton() {
// // // //         window.__ocrRunningEntryId = null;
// // // //         if (btn) btn.classList.remove("ocr-running");
// // // //     }

// // // //     // ---------- Helpers ----------
// // // //     function getXsrfToken() {
// // // //         var match = document.cookie.match(/(?:^|;\s*)XSRF-TOKEN=([^;]*)/);
// // // //         return match ? decodeURIComponent(match[1]) : "";
// // // //     }

// // // //     function postJson(url, body) {
// // // //         return fetch(url, {
// // // //             method: "POST",
// // // //             credentials: "same-origin",
// // // //             headers: {
// // // //                 "Content-Type": "application/json;charset=UTF-8",
// // // //                 "Lf-Repository": repoName,
// // // //                 "X-Lf-Repo-ID": repoName,
// // // //                 "X-XSRF-TOKEN": getXsrfToken()
// // // //             },
// // // //             body: JSON.stringify(body)
// // // //         }).then(function (r) {
// // // //             if (!r.ok) throw new Error("طلب الشبكة فشل (" + r.status + "): " + url);
// // // //             return r.json();
// // // //         });
// // // //     }

// // // //     function sleep(ms) {
// // // //         return new Promise(function (resolve) { setTimeout(resolve, ms); });
// // // //     }

// // // //     // ================= الحصول على معرّفات كل الصفحات =================
// // // //     //
// // // //     // الإصدار القديم كان بياخد pageId واحد بس (الصفحة المعروضة) من resource
// // // //     // timing، وبيكتب نص المستند كله فيه. يعني حتى لو الـ OCR رجّع 5 صفحات،
// // // //     // الخمسة كانوا بيتلزقوا في صفحة 1 والباقي بيفضل فاضي.

// // // //     function scrapePageIdsFromResourceTiming() {
// // // //         // الصفحات اللي اتعرضت (أو اتحمّلت الـ thumbnails بتاعتها) بتسيب
// // // //         // أثرها في resource timing. مش مضمون إنها كل الصفحات - ده fallback.
// // // //         var ids = [];
// // // //         try {
// // // //             var resources = performance.getEntriesByType("resource");
// // // //             for (var i = 0; i < resources.length; i++) {
// // // //                 var url = resources[i].name;
// // // //                 if (url.indexOf("documentId=" + entryId) === -1 &&
// // // //                     url.indexOf("docId=" + entryId) === -1) continue;
// // // //                 if (url.indexOf("TileData.aspx") === -1 &&
// // // //                     url.indexOf("Thumbnail") === -1) continue;
// // // //                 var m = url.match(/[?&]pageId=([^&]+)/);
// // // //                 if (m && ids.indexOf(m[1]) === -1) ids.push(m[1]);
// // // //             }
// // // //         } catch (e) {
// // // //             console.warn("ArabicOCR: تعذر قراءة pageIds من resource timing -", e);
// // // //         }
// // // //         return ids;
// // // //     }

// // // //     function fetchPageIds() {
// // // //         // 🔧 لازم تتأكد من اسم الـ endpoint الصحيح في نسختك من Web Access.
// // // //         // شغّل الـ probe ده مرة واحدة في الـ console وشوف مين بيرد بـ array
// // // //         // فيه page ids، وبعدين سيب الاسم الصحيح بس في المصفوفة دي:
// // // //         //
// // // //         //   ["GetDocumentInfo","GetDocInfo","GetPages","GetPageInfo"]
// // // //         //     .forEach(m => fetch("/laserfiche/DocumentService.ashx/"+m, {...}))
// // // //         //
// // // //         var candidates = ["GetDocumentInfo", "GetDocInfo", "GetPages", "GetPageInfo"];

// // // //         function tryNext(index) {
// // // //             if (index >= candidates.length) return Promise.resolve(null);
// // // //             return postJson("/laserfiche/DocumentService.ashx/" + candidates[index], {
// // // //                 repoName: repoName,
// // // //                 documentId: entryId
// // // //             }).then(function (result) {
// // // //                 var payload = result && result.d;
// // // //                 var pages = payload && (payload.Pages || payload.pages || payload.PageInfos);
// // // //                 if (pages && pages.length) {
// // // //                     var ids = pages.map(function (p) {
// // // //                         return String(p.Id || p.id || p.PageId || p.pageId);
// // // //                     }).filter(function (v) { return v && v !== "undefined"; });
// // // //                     if (ids.length) {
// // // //                         console.log("ArabicOCR: pageIds من " + candidates[index] + ":", ids);
// // // //                         return ids;
// // // //                     }
// // // //                 }
// // // //                 return tryNext(index + 1);
// // // //             }).catch(function () {
// // // //                 return tryNext(index + 1);
// // // //             });
// // // //         }

// // // //         return tryNext(0).then(function (ids) {
// // // //             if (ids && ids.length) return ids;
// // // //             var scraped = scrapePageIdsFromResourceTiming();
// // // //             console.warn(
// // // //                 "ArabicOCR: مفيش endpoint رجّع قائمة الصفحات، هنستخدم اللي في " +
// // // //                 "resource timing (" + scraped.length + " صفحة). لو المستند أكتر من كده، " +
// // // //                 "افتح بانل الـ Thumbnails ونزّل لآخره الأول."
// // // //             );
// // // //             return scraped;
// // // //         });
// // // //     }

// // // //     function saveAllPagesText(pageIds, pagesArr) {
// // // //         if (!pageIds || !pageIds.length) {
// // // //             textError = "تعذر الحصول على معرّفات صفحات المستند";
// // // //             return Promise.resolve();
// // // //         }
// // // //         if (!pagesArr || !pagesArr.length) return Promise.resolve();

// // // //         if (pageIds.length !== pagesArr.length) {
// // // //             textError = "عدد صفحات Laserfiche (" + pageIds.length +
// // // //                         ") لا يطابق عدد صفحات الـ OCR (" + pagesArr.length + ")";
// // // //             console.warn("ArabicOCR: " + textError);
// // // //         }

// // // //         var count = Math.min(pageIds.length, pagesArr.length);
// // // //         var chain = Promise.resolve();
// // // //         for (var i = 0; i < count; i++) {
// // // //             (function (idx) {
// // // //                 chain = chain.then(function () {
// // // //                     if (!pagesArr[idx].text) return null;
// // // //                     return postJson("/laserfiche/DocumentService.ashx/SetTextByDocIdAndPageId", {
// // // //                         repoName: repoName,
// // // //                         documentId: entryId,
// // // //                         strPageId: String(pageIds[idx]),
// // // //                         newText: pagesArr[idx].text,
// // // //                         hints: []
// // // //                     });
// // // //                 });
// // // //             })(i);
// // // //         }
// // // //         return chain.catch(function (err) {
// // // //             textError = "فشل حفظ نص إحدى الصفحات: " + (err && err.message);
// // // //             console.warn("ArabicOCR: " + textError);
// // // //         });
// // // //     }

// // // //     function refreshSessionBeforeSave() {
// // // //         return postJson("/laserfiche/MetadataService.ashx/GetMetadata", {
// // // //             repoName: repoName,
// // // //             entryIds: [String(entryId)],
// // // //             metadataFlags: 1
// // // //         }).catch(function (err) {
// // // //             console.warn("ArabicOCR: فشل تجديد الجلسة قبل الحفظ -", err);
// // // //         });
// // // //     }

// // // //     function unlockDocument() {
// // // //         if (!documentWasLocked) return Promise.resolve();
// // // //         return postJson("/laserfiche/DocumentService.ashx/UnlockDocument", {
// // // //             repoName: repoName,
// // // //             documentId: entryId
// // // //         }).then(function (result) {
// // // //             documentWasLocked = false;
// // // //             return result;
// // // //         }).catch(function (err) {
// // // //             console.warn("ArabicOCR: فشل فك القفل عن المستند -", err);
// // // //         });
// // // //     }

// // // //     function startExport() {
// // // //         var url = "/laserfiche/Dialogs/Export/ExportDisplay.aspx"
// // // //             + "?r=" + encodeURIComponent(repoName)
// // // //             + "&t=1&i=" + entryId + "&v=0&p=" + EXPORT_PAGES_PARAM
// // // //             + "&f=3&optToken=&sh=&loc=0&sep=&reportFormat=&e=";
// // // //         return fetch(url, { credentials: "same-origin" })
// // // //             .then(function (r) {
// // // //                 if (!r.ok) throw new Error("فشل بدء عملية التصدير (" + r.status + ")");
// // // //                 return r.text();
// // // //             })
// // // //             .then(function (html) {
// // // //                 var m = html.match(/exportToken&quot;:&quot;([a-f0-9-]+)&quot;/i)
// // // //                       || html.match(/"exportToken"\s*:\s*"([a-f0-9-]+)"/i);
// // // //                 if (!m) throw new Error("تعذر الحصول على exportToken");
// // // //                 return m[1];
// // // //             });
// // // //     }

// // // //     function waitForExport(token) {
// // // //         var attempts = 0;
// // // //         function check() {
// // // //             attempts++;
// // // //             if (attempts > 40) throw new Error("انتهت مهلة انتظار التصدير (Timeout)");
// // // //             return postJson("/laserfiche/ExportService.ashx/GetExportStatus", {
// // // //                 repoName: repoName,
// // // //                 token: token
// // // //             }).then(function (statusResult) {
// // // //                 var s = statusResult.d;
// // // //                 if (!s) throw new Error("استجابة غير متوقعة أثناء التصدير");
// // // //                 if (s.State === 2 || s.Completion === 100) return token;
// // // //                 if (s.FailMsg) throw new Error("فشل التصدير: " + s.FailMsg);
// // // //                 return sleep(500).then(check);
// // // //             });
// // // //         }
// // // //         return check();
// // // //     }

// // // //     function downloadExportedFile(token) {
// // // //         var url = "/laserfiche/Dialogs/Export/GetExportFile.aspx?token="
// // // //             + encodeURIComponent(token) + "&repo=" + encodeURIComponent(repoName);
// // // //         return fetch(url, { credentials: "same-origin" })
// // // //             .then(function (r) {
// // // //                 if (!r.ok) throw new Error("فشل تحميل الملف المُصدَّر (" + r.status + ")");
// // // //                 return r.blob();
// // // //             });
// // // //     }

// // // //     function callOcrService(path, formData) {
// // // //         return fetch(OCR_SERVICE_URL + path, { method: "POST", body: formData })
// // // //             .then(function (r) {
// // // //                 if (!r.ok) {
// // // //                     return r.text().then(function (t) {
// // // //                         throw new Error("خدمة الـ OCR رفضت الطلب (" + r.status + "): " + (t || "").slice(0, 300));
// // // //                     });
// // // //                 }
// // // //                 return r.json();
// // // //             })
// // // //             .catch(function (err) {
// // // //                 if (err.message && err.message.indexOf("خدمة الـ OCR") === 0) throw err;
// // // //                 throw new Error("تعذر الاتصال بخدمة الـ OCR المحلية (تأكد إن السيرفر شغال على " + OCR_SERVICE_URL + ")");
// // // //             });
// // // //     }

// // // //     // ================= التنفيذ الفعلي =================

// // // //     if (typeof webAccessApi === "undefined" || !webAccessApi.getFocusedEntries) {
// // // //         alert("حدث خطأ: واجهة WebAccess غير متاحة في هذه الصفحة");
// // // //         return;
// // // //     }

// // // //     var entries;
// // // //     try {
// // // //         entries = webAccessApi.getFocusedEntries();
// // // //     } catch (e) {
// // // //         alert("تعذر قراءة المستند المحدد");
// // // //         return;
// // // //     }

// // // //     if (!entries || entries.length === 0) { alert("رجاء اختيار مستند أولاً"); return; }
// // // //     if (entries.length > 1) { alert("رجاء اختيار مستند واحد فقط"); return; }

// // // //     entryId = entries[0].id;

// // // //     if (window.__ocrRunningEntryId === entryId) return;
// // // //     window.__ocrRunningEntryId = entryId;
// // // //     if (btn) btn.classList.add("ocr-running");

// // // //     var fieldsById = {};
// // // //     var pageIds = [];

// // // //     showOverlayLoading("جاري قراءة بيانات القالب...");

// // // //     postJson("/laserfiche/MetadataService.ashx/GetMetadata", {
// // // //         repoName: repoName,
// // // //         entryIds: [String(entryId)],
// // // //         metadataFlags: 1
// // // //     })
// // // //     .then(function (metaResult) {
// // // //         if (!metaResult || !metaResult.d || !metaResult.d.Fields) {
// // // //             throw new Error("لا يمكن قراءة حقول القالب لهذا المستند (تأكد إن له قالب)");
// // // //         }
// // // //         (metaResult.d.Fields.templateFields || []).forEach(function (f) {
// // // //             fieldsById[f.name] = f.id;
// // // //         });
// // // //         return fetchPageIds();
// // // //     })
// // // //     .then(function (ids) {
// // // //         pageIds = ids || [];
// // // //         console.log("ArabicOCR: عدد صفحات المستند في Laserfiche =", pageIds.length);
// // // //         showOverlayLoading("جاري تصدير المستند...");
// // // //         return startExport();
// // // //     })
// // // //     .then(function (token) {
// // // //         showOverlayLoading("جاري تجهيز الصورة للتحليل...");
// // // //         return waitForExport(token).then(downloadExportedFile);
// // // //     })
// // // //     .then(function (pdfBlob) {
// // // //         if (!pdfBlob || pdfBlob.size === 0) {
// // // //             throw new Error("الملف المُصدَّر فارغ، تعذر المتابعة");
// // // //         }
// // // //         console.log("ArabicOCR: حجم الملف المُصدَّر =", pdfBlob.size, "بايت");

// // // //         showOverlayLoading("جاري تحليل المستند بالذكاء الاصطناعي...\nقد تستغرق العملية بعض الوقت، برجاء الانتظار.");

// // // //         var fieldsFormData = new FormData();
// // // //         fieldsFormData.append("image", pdfBlob, "page.pdf");
// // // //         fieldsFormData.append("fields", Object.keys(fieldsById).join(","));

// // // //         var allTextFormData = new FormData();
// // // //         allTextFormData.append("image", pdfBlob, "page.pdf");

// // // //         var extractFieldsPromise = callOcrService("/extract", fieldsFormData);

// // // //         // ⚠ الإصدار القديم كان بيبلع الخطأ هنا بـ console.warn وبيرجّع null،
// // // //         // فلما extract_all_text كان بيقع على السيرفر (AttributeError) المستخدم
// // // //         // كان بيشوف "تم بنجاح" والـ Text pane فاضي من غير أي أثر للمشكلة.
// // // //         var extractAllTextPromise = callOcrService("/extract-all-text", allTextFormData)
// // // //             .catch(function (err) {
// // // //                 textError = (err && err.message) || "خطأ غير معروف";
// // // //                 console.error("ArabicOCR: /extract-all-text فشل -", err);
// // // //                 return null;
// // // //             });

// // // //         return Promise.all([extractFieldsPromise, extractAllTextPromise]);
// // // //     })
// // // //     .then(function (results) {
// // // //         var extracted = results[0] || {};
// // // //         var allTextResult = results[1];

// // // //         if (allTextResult) {
// // // //             console.log("ArabicOCR: عدد الصفحات اللي وصلت للـ OCR =", allTextResult.page_count);
// // // //             // لو الرقم ده = 1 والمستند أكتر من صفحة، يبقى المشكلة في
// // // //             // EXPORT_PAGES_PARAM فوق مش في خدمة الـ OCR.
// // // //             if (allTextResult.page_count === 1 && pageIds.length > 1) {
// // // //                 textError = "التصدير رجّع صفحة واحدة بس والمستند " + pageIds.length +
// // // //                             " صفحات — راجع EXPORT_PAGES_PARAM في السكربت";
// // // //                 console.warn("ArabicOCR: " + textError);
// // // //             }
// // // //         }

// // // //         var fieldChanges = [];
// // // //         Object.keys(extracted).forEach(function (name) {
// // // //             if (fieldsById.hasOwnProperty(name) && extracted[name]) {
// // // //                 fieldChanges.push({
// // // //                     fieldId: fieldsById[name],
// // // //                     value: String(extracted[name]).trim(),
// // // //                     remove: false,
// // // //                     fieldIndex: 0
// // // //                 });
// // // //             }
// // // //         });

// // // //         var hasText = allTextResult && allTextResult.pages && allTextResult.pages.length;
// // // //         if (fieldChanges.length === 0 && !hasText) {
// // // //             showOverlayResult("لم يتم التعرف على أي حقول أو نص في هذا المستند", true, textError);
// // // //             return null;
// // // //         }

// // // //         showOverlayLoading("جاري حفظ البيانات في المستند...");

// // // //         return refreshSessionBeforeSave().then(function () {
// // // //             return postJson("/laserfiche/DocumentService.ashx/LockDocument", {
// // // //                 repoName: repoName,
// // // //                 documentId: entryId,
// // // //                 lockEfile: false,
// // // //                 autoCheckout: false
// // // //             });
// // // //         }).then(function () {
// // // //             documentWasLocked = true;
// // // //             return saveAllPagesText(pageIds, allTextResult ? allTextResult.pages : null);
// // // //         }).then(function () {
// // // //             if (fieldChanges.length === 0) {
// // // //                 return unlockDocument().then(function () { return { d: true }; });
// // // //             }
// // // //             return postJson("/laserfiche/DocumentService.ashx/SaveEntry", {
// // // //                 repoName: repoName,
// // // //                 documentId: entryId,
// // // //                 curPageNum: 0,
// // // //                 strCurPageId: 0,
// // // //                 changes: {
// // // //                     dirty: true,
// // // //                     newTemplateId: 0,
// // // //                     removeTemplate: false,
// // // //                     fieldChanges: fieldChanges,
// // // //                     tagChanges: [],
// // // //                     linkChanges: []
// // // //                 },
// // // //                 generalchanges: [],
// // // //                 annchanges: []
// // // //             }).then(function (saveResult) {
// // // //                 return unlockDocument().then(function () { return saveResult; });
// // // //             });
// // // //         });
// // // //     })
// // // //     .then(function (saveResult) {
// // // //         if (!saveResult) return;
// // // //         try { webAccessApi.refreshMetadata(); }
// // // //         catch (e) { console.warn("ArabicOCR: فشل تحديث الميتاداتا -", e); }
// // // //         try { webAccessApi.refreshContentsPane(); }
// // // //         catch (e) { console.warn("ArabicOCR: فشل تحديث Contents Pane -", e); }

// // // //         showOverlayResult(
// // // //             "تم استخراج البيانات وحفظها بنجاح ✔",
// // // //             false,
// // // //             textError ? "⚠ ملاحظة على النص الكامل:\n" + textError : null
// // // //         );

// // // //         // لو فيه مشكلة في النص، منعملش reload تلقائي عشان المستخدم يقرا التحذير.
// // // //         if (!textError) {
// // // //             setTimeout(function () { location.reload(); }, 1500);
// // // //         }
// // // //     })
// // // //     .catch(function (err) {
// // // //         console.error("ArabicOCR Error:", err);
// // // //         unlockDocument().then(function () {
// // // //             showOverlayResult("حدث خطأ:\n" + (err && err.message ? err.message : "خطأ غير متوقع"), true);
// // // //         });
// // // //     });
// // // // };


// // // window.runArabicOcrAction = function () {

// // //     var OVERLAY_ID = "arabicOcrOverlay";
// // //     var BTN_ID = "customOcrButton";
// // //     var repoName = new URLSearchParams(window.location.search).get("repo") || "demo";
// // //     var OCR_SERVICE_URL = window.location.protocol + "//" + window.location.hostname + ":8001";
// // //     var documentWasLocked = false;
// // //     var entryId = null;
// // //     var textError = null;   // سبب فشل استخراج النص الكامل، لو حصل

// // //     // ⚠⚠ مشكلة "أول صفحة بس" — اتأكدت من الـ HAR ⚠⚠
// // //     // مستند n2 عنده صفحتين، والـ PDF اللي رجع من الـ export فيه /Count 1
// // //     // وصورة واحدة بس. يعني p=1 = "الصفحة الحالية" مش "كل الصفحات".
// // //     // المشكلة في الـ export نفسه، مش في خدمة الـ OCR.
// // //     //
// // //     // "0" هو أرجح احتمال لـ "All pages". لو مرجعش الصفحتين، هات القيمة
// // //     // المؤكدة كده: Export من واجهة Laserfiche نفسها → اختار "All pages" →
// // //     // شوف قيمة p في الـ Network tab.
// // //     var EXPORT_PAGES_PARAM = "0";

// // //     // ---------- Overlay UI ----------
// // //     function ensureOverlayStyles() {
// // //         if (document.getElementById("arabicOcrOverlayStyles")) return;
// // //         var style = document.createElement("style");
// // //         style.id = "arabicOcrOverlayStyles";
// // //         style.innerHTML =
// // //             "#" + OVERLAY_ID + "{position:fixed;top:0;left:0;width:100%;height:100%;" +
// // //             "background:rgba(0,0,0,0.55);z-index:2147483647;display:flex;" +
// // //             "align-items:center;justify-content:center;font-family:Tahoma,Arial,sans-serif;}" +
// // //             "#" + OVERLAY_ID + " .aoBox{background:#fff;border-radius:10px;padding:28px 32px;" +
// // //             "min-width:280px;max-width:420px;text-align:center;box-shadow:0 6px 24px rgba(0,0,0,0.3);direction:rtl;}" +
// // //             "#" + OVERLAY_ID + " .aoSpinner{width:42px;height:42px;margin:0 auto 16px;" +
// // //             "border:4px solid #ddd;border-top-color:#2b6cb0;border-radius:50%;" +
// // //             "animation:aoSpin 0.9s linear infinite;}" +
// // //             "@keyframes aoSpin{to{transform:rotate(360deg);}}" +
// // //             "#" + OVERLAY_ID + " .aoMsg{font-size:15px;color:#222;margin-bottom:4px;white-space:pre-line;}" +
// // //             "#" + OVERLAY_ID + " .aoIcon{font-size:38px;margin-bottom:10px;}" +
// // //             "#" + OVERLAY_ID + " .aoClose{margin-top:16px;padding:8px 22px;border:none;" +
// // //             "border-radius:6px;background:#2b6cb0;color:#fff;font-size:14px;cursor:pointer;}" +
// // //             "#" + OVERLAY_ID + " .aoClose.error{background:#c53030;}" +
// // //             "#" + OVERLAY_ID + " .aoWarn{margin-top:10px;font-size:13px;color:#b7791f;" +
// // //             "white-space:pre-line;direction:rtl;}";
// // //         document.head.appendChild(style);
// // //     }

// // //     function getOverlayEl() {
// // //         var overlay = document.getElementById(OVERLAY_ID);
// // //         if (!overlay) {
// // //             overlay = document.createElement("div");
// // //             overlay.id = OVERLAY_ID;
// // //             document.body.appendChild(overlay);
// // //         }
// // //         return overlay;
// // //     }

// // //     function showOverlayLoading(message) {
// // //         ensureOverlayStyles();
// // //         getOverlayEl().innerHTML =
// // //             '<div class="aoBox"><div class="aoSpinner"></div><div class="aoMsg">' +
// // //             message + "</div></div>";
// // //     }

// // //     function showOverlayResult(message, isError, warning) {
// // //         ensureOverlayStyles();
// // //         var overlay = getOverlayEl();
// // //         var icon = isError ? "\u26A0\uFE0F" : "\u2705";
// // //         overlay.innerHTML =
// // //             '<div class="aoBox"><div class="aoIcon">' + icon + '</div><div class="aoMsg">' +
// // //             message + '</div>' +
// // //             (warning ? '<div class="aoWarn">' + warning + '</div>' : '') +
// // //             '<button class="aoClose' + (isError ? " error" : "") +
// // //             '" id="aoCloseBtn">تم</button></div>';
// // //         document.getElementById("aoCloseBtn").onclick = hideOverlay;
// // //         unlockButton();
// // //     }

// // //     function hideOverlay() {
// // //         var overlay = document.getElementById(OVERLAY_ID);
// // //         if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
// // //     }

// // //     // ---------- منع الضغط المزدوج (مربوط بالمستند الحالي فقط) ----------
// // //     var btn = document.getElementById(BTN_ID);

// // //     function unlockButton() {
// // //         window.__ocrRunningEntryId = null;
// // //         if (btn) btn.classList.remove("ocr-running");
// // //     }

// // //     // ---------- Helpers ----------
// // //     function getXsrfToken() {
// // //         var match = document.cookie.match(/(?:^|;\s*)XSRF-TOKEN=([^;]*)/);
// // //         return match ? decodeURIComponent(match[1]) : "";
// // //     }

// // //     function postJson(url, body) {
// // //         return fetch(url, {
// // //             method: "POST",
// // //             credentials: "same-origin",
// // //             headers: {
// // //                 "Content-Type": "application/json;charset=UTF-8",
// // //                 "Lf-Repository": repoName,
// // //                 "X-Lf-Repo-ID": repoName,
// // //                 "X-XSRF-TOKEN": getXsrfToken()
// // //             },
// // //             body: JSON.stringify(body)
// // //         }).then(function (r) {
// // //             if (!r.ok) throw new Error("طلب الشبكة فشل (" + r.status + "): " + url);
// // //             return r.json();
// // //         });
// // //     }

// // //     function sleep(ms) {
// // //         return new Promise(function (resolve) { setTimeout(resolve, ms); });
// // //     }

// // //     // ================= الحصول على معرّفات كل الصفحات =================
// // //     //
// // //     // الإصدار القديم كان بياخد pageId واحد بس (الصفحة المعروضة) من resource
// // //     // timing، وبيكتب نص المستند كله فيه. يعني حتى لو الـ OCR رجّع 5 صفحات،
// // //     // الخمسة كانوا بيتلزقوا في صفحة 1 والباقي بيفضل فاضي.

// // //     function scrapePageIdsFromResourceTiming() {
// // //         // الصفحات اللي اتعرضت (أو اتحمّلت الـ thumbnails بتاعتها) بتسيب
// // //         // أثرها في resource timing. مش مضمون إنها كل الصفحات - ده fallback.
// // //         var ids = [];
// // //         try {
// // //             var resources = performance.getEntriesByType("resource");
// // //             for (var i = 0; i < resources.length; i++) {
// // //                 var url = resources[i].name;
// // //                 if (url.indexOf("documentId=" + entryId) === -1 &&
// // //                     url.indexOf("docId=" + entryId) === -1) continue;
// // //                 if (url.indexOf("TileData.aspx") === -1 &&
// // //                     url.indexOf("Thumbnail") === -1) continue;
// // //                 var m = url.match(/[?&]pageId=([^&]+)/);
// // //                 if (m && ids.indexOf(m[1]) === -1) ids.push(m[1]);
// // //             }
// // //         } catch (e) {
// // //             console.warn("ArabicOCR: تعذر قراءة pageIds من resource timing -", e);
// // //         }
// // //         return ids;
// // //     }

// // //     function fetchPageIds() {
// // //         // ❌ الأربع endpoints اللي كانوا هنا (GetDocumentInfo / GetDocInfo /
// // //         // GetPages / GetPageInfo) كلهم رجّعوا 500 "Unknown Error" في الـ HAR
// // //         // — يعني مش موجودين في نسختك من Web Access. اتشالوا.
// // //         //
// // //         // البديل: resource timing. الصفحة المعروضة وكل thumbnail اتحمّل
// // //         // بيسيبوا URL فيه pageId. عشان يطلعوا كلهم، لازم بانل الـ Thumbnails
// // //         // يكون مفتوح (وهو مفتوح عندك في الشاشة).
// // //         var ids = scrapePageIdsFromResourceTiming();
// // //         if (!ids.length) {
// // //             console.warn(
// // //                 "ArabicOCR: مفيش أي pageId في resource timing. افتح بانل " +
// // //                 "الـ Thumbnails ونزّل لآخره، وبعدين شغّل الزرار تاني.\n" +
// // //                 "لاستكشاف الشكل الحقيقي للـ URLs شغّل: __ocrDumpPageUrls()"
// // //             );
// // //         }
// // //         return Promise.resolve(ids);
// // //     }

// // //     // أداة تشخيص: بتطبع كل الـ URLs اللي فيها pageId عشان تعرف مين بيخدم
// // //     // الصفحات في نسختك وتبني عليه. شغّلها من الـ console.
// // //     window.__ocrDumpPageUrls = function () {
// // //         var urls = performance.getEntriesByType("resource")
// // //             .map(function (r) { return r.name; })
// // //             .filter(function (n) { return /pageId=/i.test(n); });
// // //         console.table(urls);
// // //         return urls;
// // //     };

// // //     function saveAllPagesText(pageIds, pagesArr) {
// // //         if (!pageIds || !pageIds.length) {
// // //             textError = "تعذر الحصول على معرّفات صفحات المستند";
// // //             return Promise.resolve();
// // //         }
// // //         if (!pagesArr || !pagesArr.length) return Promise.resolve();

// // //         if (pageIds.length !== pagesArr.length) {
// // //             textError = "عدد صفحات Laserfiche (" + pageIds.length +
// // //                         ") لا يطابق عدد صفحات الـ OCR (" + pagesArr.length + ")";
// // //             console.warn("ArabicOCR: " + textError);
// // //         }

// // //         var count = Math.min(pageIds.length, pagesArr.length);
// // //         var chain = Promise.resolve();
// // //         for (var i = 0; i < count; i++) {
// // //             (function (idx) {
// // //                 chain = chain.then(function () {
// // //                     if (!pagesArr[idx].text) return null;
// // //                     return postJson("/laserfiche/DocumentService.ashx/SetTextByDocIdAndPageId", {
// // //                         repoName: repoName,
// // //                         documentId: entryId,
// // //                         strPageId: String(pageIds[idx]),
// // //                         newText: pagesArr[idx].text,
// // //                         hints: []
// // //                     });
// // //                 });
// // //             })(i);
// // //         }
// // //         return chain.catch(function (err) {
// // //             textError = "فشل حفظ نص إحدى الصفحات: " + (err && err.message);
// // //             console.warn("ArabicOCR: " + textError);
// // //         });
// // //     }

// // //     function refreshSessionBeforeSave() {
// // //         return postJson("/laserfiche/MetadataService.ashx/GetMetadata", {
// // //             repoName: repoName,
// // //             entryIds: [String(entryId)],
// // //             metadataFlags: 1
// // //         }).catch(function (err) {
// // //             console.warn("ArabicOCR: فشل تجديد الجلسة قبل الحفظ -", err);
// // //         });
// // //     }

// // //     function unlockDocument() {
// // //         if (!documentWasLocked) return Promise.resolve();
// // //         return postJson("/laserfiche/DocumentService.ashx/UnlockDocument", {
// // //             repoName: repoName,
// // //             documentId: entryId
// // //         }).then(function (result) {
// // //             documentWasLocked = false;
// // //             return result;
// // //         }).catch(function (err) {
// // //             console.warn("ArabicOCR: فشل فك القفل عن المستند -", err);
// // //         });
// // //     }

// // //     function startExport() {
// // //         var url = "/laserfiche/Dialogs/Export/ExportDisplay.aspx"
// // //             + "?r=" + encodeURIComponent(repoName)
// // //             + "&t=1&i=" + entryId + "&v=0&p=" + EXPORT_PAGES_PARAM
// // //             + "&f=3&optToken=&sh=&loc=0&sep=&reportFormat=&e=";
// // //         return fetch(url, { credentials: "same-origin" })
// // //             .then(function (r) {
// // //                 if (!r.ok) throw new Error("فشل بدء عملية التصدير (" + r.status + ")");
// // //                 return r.text();
// // //             })
// // //             .then(function (html) {
// // //                 var m = html.match(/exportToken&quot;:&quot;([a-f0-9-]+)&quot;/i)
// // //                       || html.match(/"exportToken"\s*:\s*"([a-f0-9-]+)"/i);
// // //                 if (!m) throw new Error("تعذر الحصول على exportToken");
// // //                 return m[1];
// // //             });
// // //     }

// // //     function waitForExport(token) {
// // //         var attempts = 0;
// // //         function check() {
// // //             attempts++;
// // //             if (attempts > 40) throw new Error("انتهت مهلة انتظار التصدير (Timeout)");
// // //             return postJson("/laserfiche/ExportService.ashx/GetExportStatus", {
// // //                 repoName: repoName,
// // //                 token: token
// // //             }).then(function (statusResult) {
// // //                 var s = statusResult.d;
// // //                 if (!s) throw new Error("استجابة غير متوقعة أثناء التصدير");
// // //                 if (s.State === 2 || s.Completion === 100) return token;
// // //                 if (s.FailMsg) throw new Error("فشل التصدير: " + s.FailMsg);
// // //                 return sleep(500).then(check);
// // //             });
// // //         }
// // //         return check();
// // //     }

// // //     function downloadExportedFile(token) {
// // //         var url = "/laserfiche/Dialogs/Export/GetExportFile.aspx?token="
// // //             + encodeURIComponent(token) + "&repo=" + encodeURIComponent(repoName);
// // //         return fetch(url, { credentials: "same-origin" })
// // //             .then(function (r) {
// // //                 if (!r.ok) throw new Error("فشل تحميل الملف المُصدَّر (" + r.status + ")");
// // //                 return r.blob();
// // //             });
// // //     }

// // //     function callOcrService(path, formData) {
// // //         return fetch(OCR_SERVICE_URL + path, { method: "POST", body: formData })
// // //             .then(function (r) {
// // //                 if (!r.ok) {
// // //                     return r.text().then(function (t) {
// // //                         throw new Error("خدمة الـ OCR رفضت الطلب (" + r.status + "): " + (t || "").slice(0, 300));
// // //                     });
// // //                 }
// // //                 return r.json();
// // //             })
// // //             .catch(function (err) {
// // //                 if (err.message && err.message.indexOf("خدمة الـ OCR") === 0) throw err;
// // //                 throw new Error("تعذر الاتصال بخدمة الـ OCR المحلية (تأكد إن السيرفر شغال على " + OCR_SERVICE_URL + ")");
// // //             });
// // //     }

// // //     // ================= التنفيذ الفعلي =================

// // //     if (typeof webAccessApi === "undefined" || !webAccessApi.getFocusedEntries) {
// // //         alert("حدث خطأ: واجهة WebAccess غير متاحة في هذه الصفحة");
// // //         return;
// // //     }

// // //     var entries;
// // //     try {
// // //         entries = webAccessApi.getFocusedEntries();
// // //     } catch (e) {
// // //         alert("تعذر قراءة المستند المحدد");
// // //         return;
// // //     }

// // //     if (!entries || entries.length === 0) { alert("رجاء اختيار مستند أولاً"); return; }
// // //     if (entries.length > 1) { alert("رجاء اختيار مستند واحد فقط"); return; }

// // //     entryId = entries[0].id;

// // //     if (window.__ocrRunningEntryId === entryId) return;
// // //     window.__ocrRunningEntryId = entryId;
// // //     if (btn) btn.classList.add("ocr-running");

// // //     var fieldsById = {};
// // //     var pageIds = [];

// // //     showOverlayLoading("جاري قراءة بيانات القالب...");

// // //     postJson("/laserfiche/MetadataService.ashx/GetMetadata", {
// // //         repoName: repoName,
// // //         entryIds: [String(entryId)],
// // //         metadataFlags: 1
// // //     })
// // //     .then(function (metaResult) {
// // //         if (!metaResult || !metaResult.d || !metaResult.d.Fields) {
// // //             throw new Error("لا يمكن قراءة حقول القالب لهذا المستند (تأكد إن له قالب)");
// // //         }
// // //         (metaResult.d.Fields.templateFields || []).forEach(function (f) {
// // //             fieldsById[f.name] = f.id;
// // //         });
// // //         return fetchPageIds();
// // //     })
// // //     .then(function (ids) {
// // //         pageIds = ids || [];
// // //         console.log("ArabicOCR: عدد صفحات المستند في Laserfiche =", pageIds.length);
// // //         showOverlayLoading("جاري تصدير المستند...");
// // //         return startExport();
// // //     })
// // //     .then(function (token) {
// // //         showOverlayLoading("جاري تجهيز الصورة للتحليل...");
// // //         return waitForExport(token).then(downloadExportedFile);
// // //     })
// // //     .then(function (pdfBlob) {
// // //         if (!pdfBlob || pdfBlob.size === 0) {
// // //             throw new Error("الملف المُصدَّر فارغ، تعذر المتابعة");
// // //         }
// // //         console.log("ArabicOCR: حجم الملف المُصدَّر =", pdfBlob.size, "بايت");

// // //         showOverlayLoading("جاري تحليل المستند بالذكاء الاصطناعي...\nقد تستغرق العملية بعض الوقت، برجاء الانتظار.");

// // //         var fieldsFormData = new FormData();
// // //         fieldsFormData.append("image", pdfBlob, "page.pdf");
// // //         fieldsFormData.append("fields", Object.keys(fieldsById).join(","));

// // //         var allTextFormData = new FormData();
// // //         allTextFormData.append("image", pdfBlob, "page.pdf");

// // //         var extractFieldsPromise = callOcrService("/extract", fieldsFormData);

// // //         // ⚠ الإصدار القديم كان بيبلع الخطأ هنا بـ console.warn وبيرجّع null،
// // //         // فلما extract_all_text كان بيقع على السيرفر (AttributeError) المستخدم
// // //         // كان بيشوف "تم بنجاح" والـ Text pane فاضي من غير أي أثر للمشكلة.
// // //         var extractAllTextPromise = callOcrService("/extract-all-text", allTextFormData)
// // //             .catch(function (err) {
// // //                 textError = (err && err.message) || "خطأ غير معروف";
// // //                 console.error("ArabicOCR: /extract-all-text فشل -", err);
// // //                 return null;
// // //             });

// // //         return Promise.all([extractFieldsPromise, extractAllTextPromise]);
// // //     })
// // //     .then(function (results) {
// // //         var extracted = results[0] || {};
// // //         var allTextResult = results[1];

// // //         if (allTextResult) {
// // //             console.log("ArabicOCR: عدد الصفحات اللي وصلت للـ OCR =", allTextResult.page_count);
// // //             // لو الرقم ده = 1 والمستند أكتر من صفحة، يبقى المشكلة في
// // //             // EXPORT_PAGES_PARAM فوق مش في خدمة الـ OCR.
// // //             if (allTextResult.page_count === 1 && pageIds.length > 1) {
// // //                 textError = "التصدير رجّع صفحة واحدة بس والمستند " + pageIds.length +
// // //                             " صفحات — راجع EXPORT_PAGES_PARAM في السكربت";
// // //                 console.warn("ArabicOCR: " + textError);
// // //             }
// // //         }

// // //         var fieldChanges = [];
// // //         Object.keys(extracted).forEach(function (name) {
// // //             if (fieldsById.hasOwnProperty(name) && extracted[name]) {
// // //                 fieldChanges.push({
// // //                     fieldId: fieldsById[name],
// // //                     value: String(extracted[name]).trim(),
// // //                     remove: false,
// // //                     fieldIndex: 0
// // //                 });
// // //             }
// // //         });

// // //         var hasText = allTextResult && allTextResult.pages && allTextResult.pages.length;
// // //         if (fieldChanges.length === 0 && !hasText) {
// // //             showOverlayResult("لم يتم التعرف على أي حقول أو نص في هذا المستند", true, textError);
// // //             return null;
// // //         }

// // //         showOverlayLoading("جاري حفظ البيانات في المستند...");

// // //         return refreshSessionBeforeSave().then(function () {
// // //             return postJson("/laserfiche/DocumentService.ashx/LockDocument", {
// // //                 repoName: repoName,
// // //                 documentId: entryId,
// // //                 lockEfile: false,
// // //                 autoCheckout: false
// // //             });
// // //         }).then(function () {
// // //             documentWasLocked = true;
// // //             return saveAllPagesText(pageIds, allTextResult ? allTextResult.pages : null);
// // //         }).then(function () {
// // //             if (fieldChanges.length === 0) {
// // //                 return unlockDocument().then(function () { return { d: true }; });
// // //             }
// // //             return postJson("/laserfiche/DocumentService.ashx/SaveEntry", {
// // //                 repoName: repoName,
// // //                 documentId: entryId,
// // //                 curPageNum: 0,
// // //                 strCurPageId: 0,
// // //                 changes: {
// // //                     dirty: true,
// // //                     newTemplateId: 0,
// // //                     removeTemplate: false,
// // //                     fieldChanges: fieldChanges,
// // //                     tagChanges: [],
// // //                     linkChanges: []
// // //                 },
// // //                 generalchanges: [],
// // //                 annchanges: []
// // //             }).then(function (saveResult) {
// // //                 return unlockDocument().then(function () { return saveResult; });
// // //             });
// // //         });
// // //     })
// // //     .then(function (saveResult) {
// // //         if (!saveResult) return;
// // //         try { webAccessApi.refreshMetadata(); }
// // //         catch (e) { console.warn("ArabicOCR: فشل تحديث الميتاداتا -", e); }
// // //         try { webAccessApi.refreshContentsPane(); }
// // //         catch (e) { console.warn("ArabicOCR: فشل تحديث Contents Pane -", e); }

// // //         showOverlayResult(
// // //             "تم استخراج البيانات وحفظها بنجاح ✔",
// // //             false,
// // //             textError ? "⚠ ملاحظة على النص الكامل:\n" + textError : null
// // //         );

// // //         // لو فيه مشكلة في النص، منعملش reload تلقائي عشان المستخدم يقرا التحذير.
// // //         if (!textError) {
// // //             setTimeout(function () { location.reload(); }, 1500);
// // //         }
// // //     })
// // //     .catch(function (err) {
// // //         console.error("ArabicOCR Error:", err);
// // //         unlockDocument().then(function () {
// // //             showOverlayResult("حدث خطأ:\n" + (err && err.message ? err.message : "خطأ غير متوقع"), true);
// // //         });
// // //     });
// // // };

// // window.runArabicOcrAction = function () {

// //     var OVERLAY_ID = "arabicOcrOverlay";
// //     var BTN_ID = "customOcrButton";
// //     var repoName = new URLSearchParams(window.location.search).get("repo") || "demo";
// //     var OCR_SERVICE_URL = window.location.protocol + "//" + window.location.hostname + ":8001";
// //     var documentWasLocked = false;
// //     var entryId = null;
// //     var textError = null;   // سبب فشل استخراج النص الكامل، لو حصل

// //     // ⚠⚠ مشكلة "أول صفحة بس" — اتأكدت من الـ HAR ⚠⚠
// //     // مستند n2 عنده صفحتين، والـ PDF اللي رجع من الـ export فيه /Count 1
// //     // وصورة واحدة بس. يعني p=1 = "الصفحة الحالية" مش "كل الصفحات".
// //     // المشكلة في الـ export نفسه، مش في خدمة الـ OCR.
// //     //
// //     // "0" هو أرجح احتمال لـ "All pages". لو مرجعش الصفحتين، هات القيمة
// //     // المؤكدة كده: Export من واجهة Laserfiche نفسها → اختار "All pages" →
// //     // شوف قيمة p في الـ Network tab.
// //     var EXPORT_PAGES_PARAM = "0";

// //     // ---------- Overlay UI ----------
// //     function ensureOverlayStyles() {
// //         if (document.getElementById("arabicOcrOverlayStyles")) return;
// //         var style = document.createElement("style");
// //         style.id = "arabicOcrOverlayStyles";
// //         style.innerHTML =
// //             "#" + OVERLAY_ID + "{position:fixed;top:0;left:0;width:100%;height:100%;" +
// //             "background:rgba(0,0,0,0.55);z-index:2147483647;display:flex;" +
// //             "align-items:center;justify-content:center;font-family:Tahoma,Arial,sans-serif;}" +
// //             "#" + OVERLAY_ID + " .aoBox{background:#fff;border-radius:10px;padding:28px 32px;" +
// //             "min-width:280px;max-width:420px;text-align:center;box-shadow:0 6px 24px rgba(0,0,0,0.3);direction:rtl;}" +
// //             "#" + OVERLAY_ID + " .aoSpinner{width:42px;height:42px;margin:0 auto 16px;" +
// //             "border:4px solid #ddd;border-top-color:#2b6cb0;border-radius:50%;" +
// //             "animation:aoSpin 0.9s linear infinite;}" +
// //             "@keyframes aoSpin{to{transform:rotate(360deg);}}" +
// //             "#" + OVERLAY_ID + " .aoMsg{font-size:15px;color:#222;margin-bottom:4px;white-space:pre-line;}" +
// //             "#" + OVERLAY_ID + " .aoIcon{font-size:38px;margin-bottom:10px;}" +
// //             "#" + OVERLAY_ID + " .aoClose{margin-top:16px;padding:8px 22px;border:none;" +
// //             "border-radius:6px;background:#2b6cb0;color:#fff;font-size:14px;cursor:pointer;}" +
// //             "#" + OVERLAY_ID + " .aoClose.error{background:#c53030;}" +
// //             "#" + OVERLAY_ID + " .aoWarn{margin-top:10px;font-size:13px;color:#b7791f;" +
// //             "white-space:pre-line;direction:rtl;}";
// //         document.head.appendChild(style);
// //     }

// //     function getOverlayEl() {
// //         var overlay = document.getElementById(OVERLAY_ID);
// //         if (!overlay) {
// //             overlay = document.createElement("div");
// //             overlay.id = OVERLAY_ID;
// //             document.body.appendChild(overlay);
// //         }
// //         return overlay;
// //     }

// //     function showOverlayLoading(message) {
// //         ensureOverlayStyles();
// //         getOverlayEl().innerHTML =
// //             '<div class="aoBox"><div class="aoSpinner"></div><div class="aoMsg">' +
// //             message + "</div></div>";
// //     }

// //     function showOverlayResult(message, isError, warning) {
// //         ensureOverlayStyles();
// //         var overlay = getOverlayEl();
// //         var icon = isError ? "\u26A0\uFE0F" : "\u2705";
// //         overlay.innerHTML =
// //             '<div class="aoBox"><div class="aoIcon">' + icon + '</div><div class="aoMsg">' +
// //             message + '</div>' +
// //             (warning ? '<div class="aoWarn">' + warning + '</div>' : '') +
// //             '<button class="aoClose' + (isError ? " error" : "") +
// //             '" id="aoCloseBtn">تم</button></div>';
// //         document.getElementById("aoCloseBtn").onclick = hideOverlay;
// //         unlockButton();
// //     }

// //     function hideOverlay() {
// //         var overlay = document.getElementById(OVERLAY_ID);
// //         if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
// //     }

// //     // ---------- منع الضغط المزدوج (مربوط بالمستند الحالي فقط) ----------
// //     var btn = document.getElementById(BTN_ID);

// //     function unlockButton() {
// //         window.__ocrRunningEntryId = null;
// //         if (btn) btn.classList.remove("ocr-running");
// //     }

// //     // ---------- Helpers ----------
// //     function getXsrfToken() {
// //         var match = document.cookie.match(/(?:^|;\s*)XSRF-TOKEN=([^;]*)/);
// //         return match ? decodeURIComponent(match[1]) : "";
// //     }

// //     function postJson(url, body) {
// //         return fetch(url, {
// //             method: "POST",
// //             credentials: "same-origin",
// //             headers: {
// //                 "Content-Type": "application/json;charset=UTF-8",
// //                 "Lf-Repository": repoName,
// //                 "X-Lf-Repo-ID": repoName,
// //                 "X-XSRF-TOKEN": getXsrfToken()
// //             },
// //             body: JSON.stringify(body)
// //         }).then(function (r) {
// //             if (!r.ok) throw new Error("طلب الشبكة فشل (" + r.status + "): " + url);
// //             return r.json();
// //         });
// //     }

// //     function sleep(ms) {
// //         return new Promise(function (resolve) { setTimeout(resolve, ms); });
// //     }

// //     // ================= الحصول على معرّفات كل الصفحات =================
// //     //
// //     // الإصدار القديم كان بياخد pageId واحد بس (الصفحة المعروضة) من resource
// //     // timing، وبيكتب نص المستند كله فيه. يعني حتى لو الـ OCR رجّع 5 صفحات،
// //     // الخمسة كانوا بيتلزقوا في صفحة 1 والباقي بيفضل فاضي.

// //     function scrapePageIdsFromResourceTiming() {
// //         // الصفحات اللي اتعرضت (أو اتحمّلت الـ thumbnails بتاعتها) بتسيب
// //         // أثرها في resource timing. مش مضمون إنها كل الصفحات - ده fallback.
// //         var ids = [];
// //         try {
// //             var resources = performance.getEntriesByType("resource");
// //             for (var i = 0; i < resources.length; i++) {
// //                 var url = resources[i].name;
// //                 if (url.indexOf("documentId=" + entryId) === -1 &&
// //                     url.indexOf("docId=" + entryId) === -1) continue;
// //                 if (url.indexOf("TileData.aspx") === -1 &&
// //                     url.indexOf("Thumbnail") === -1) continue;
// //                 var m = url.match(/[?&]pageId=([^&]+)/);
// //                 if (m && ids.indexOf(m[1]) === -1) ids.push(m[1]);
// //             }
// //         } catch (e) {
// //             console.warn("ArabicOCR: تعذر قراءة pageIds من resource timing -", e);
// //         }
// //         return ids;
// //     }

// //     function fetchPageIds() {
// //         // ❌ الأربع endpoints اللي كانوا هنا (GetDocumentInfo / GetDocInfo /
// //         // GetPages / GetPageInfo) كلهم رجّعوا 500 "Unknown Error" في الـ HAR
// //         // — يعني مش موجودين في نسختك من Web Access. اتشالوا.
// //         //
// //         // البديل: resource timing. الصفحة المعروضة وكل thumbnail اتحمّل
// //         // بيسيبوا URL فيه pageId. عشان يطلعوا كلهم، لازم بانل الـ Thumbnails
// //         // يكون مفتوح (وهو مفتوح عندك في الشاشة).
// //         var ids = scrapePageIdsFromResourceTiming();
// //         if (!ids.length) {
// //             console.warn(
// //                 "ArabicOCR: مفيش أي pageId في resource timing. افتح بانل " +
// //                 "الـ Thumbnails ونزّل لآخره، وبعدين شغّل الزرار تاني.\n" +
// //                 "لاستكشاف الشكل الحقيقي للـ URLs شغّل: __ocrDumpPageUrls()"
// //             );
// //         }
// //         return Promise.resolve(ids);
// //     }

// //     // أداة تشخيص: بتطبع كل الـ URLs اللي فيها pageId عشان تعرف مين بيخدم
// //     // الصفحات في نسختك وتبني عليه. شغّلها من الـ console.
// //     window.__ocrDumpPageUrls = function () {
// //         var urls = performance.getEntriesByType("resource")
// //             .map(function (r) { return r.name; })
// //             .filter(function (n) { return /pageId=/i.test(n); });
// //         console.table(urls);
// //         return urls;
// //     };

// //     function saveAllPagesText(pageIds, pagesArr) {
// //         if (!pageIds || !pageIds.length) {
// //             textError = "تعذر الحصول على معرّفات صفحات المستند";
// //             return Promise.resolve();
// //         }
// //         if (!pagesArr || !pagesArr.length) return Promise.resolve();

// //         if (pageIds.length !== pagesArr.length) {
// //             textError = "عدد صفحات Laserfiche (" + pageIds.length +
// //                         ") لا يطابق عدد صفحات الـ OCR (" + pagesArr.length + ")";
// //             console.warn("ArabicOCR: " + textError);
// //         }

// //         var count = Math.min(pageIds.length, pagesArr.length);
// //         var chain = Promise.resolve();
// //         for (var i = 0; i < count; i++) {
// //             (function (idx) {
// //                 chain = chain.then(function () {
// //                     if (!pagesArr[idx].text) return null;
// //                     return postJson("/laserfiche/DocumentService.ashx/SetTextByDocIdAndPageId", {
// //                         repoName: repoName,
// //                         documentId: entryId,
// //                         strPageId: String(pageIds[idx]),
// //                         newText: pagesArr[idx].text,
// //                         hints: []
// //                     });
// //                 });
// //             })(i);
// //         }
// //         return chain.catch(function (err) {
// //             textError = "فشل حفظ نص إحدى الصفحات: " + (err && err.message);
// //             console.warn("ArabicOCR: " + textError);
// //         });
// //     }

// //     function refreshSessionBeforeSave() {
// //         return postJson("/laserfiche/MetadataService.ashx/GetMetadata", {
// //             repoName: repoName,
// //             entryIds: [String(entryId)],
// //             metadataFlags: 1
// //         }).catch(function (err) {
// //             console.warn("ArabicOCR: فشل تجديد الجلسة قبل الحفظ -", err);
// //         });
// //     }

// //     function unlockDocument() {
// //         if (!documentWasLocked) return Promise.resolve();
// //         return postJson("/laserfiche/DocumentService.ashx/UnlockDocument", {
// //             repoName: repoName,
// //             documentId: entryId
// //         }).then(function (result) {
// //             documentWasLocked = false;
// //             return result;
// //         }).catch(function (err) {
// //             console.warn("ArabicOCR: فشل فك القفل عن المستند -", err);
// //         });
// //     }

// //     function startExport() {
// //         var url = "/laserfiche/Dialogs/Export/ExportDisplay.aspx"
// //             + "?r=" + encodeURIComponent(repoName)
// //             + "&t=1&i=" + entryId + "&v=0&p=" + EXPORT_PAGES_PARAM
// //             + "&f=3&optToken=&sh=&loc=0&sep=&reportFormat=&e=";
// //         return fetch(url, { credentials: "same-origin" })
// //             .then(function (r) {
// //                 if (!r.ok) throw new Error("فشل بدء عملية التصدير (" + r.status + ")");
// //                 return r.text();
// //             })
// //             .then(function (html) {
// //                 var m = html.match(/exportToken&quot;:&quot;([a-f0-9-]+)&quot;/i)
// //                       || html.match(/"exportToken"\s*:\s*"([a-f0-9-]+)"/i);
// //                 if (!m) throw new Error("تعذر الحصول على exportToken");
// //                 return m[1];
// //             });
// //     }

// //     function waitForExport(token) {
// //         var attempts = 0;
// //         function check() {
// //             attempts++;
// //             if (attempts > 40) throw new Error("انتهت مهلة انتظار التصدير (Timeout)");
// //             return postJson("/laserfiche/ExportService.ashx/GetExportStatus", {
// //                 repoName: repoName,
// //                 token: token
// //             }).then(function (statusResult) {
// //                 var s = statusResult.d;
// //                 if (!s) throw new Error("استجابة غير متوقعة أثناء التصدير");
// //                 if (s.State === 2 || s.Completion === 100) return token;
// //                 if (s.FailMsg) throw new Error("فشل التصدير: " + s.FailMsg);
// //                 return sleep(500).then(check);
// //             });
// //         }
// //         return check();
// //     }

// //     function downloadExportedFile(token) {
// //         var url = "/laserfiche/Dialogs/Export/GetExportFile.aspx?token="
// //             + encodeURIComponent(token) + "&repo=" + encodeURIComponent(repoName);
// //         return fetch(url, { credentials: "same-origin" })
// //             .then(function (r) {
// //                 if (!r.ok) throw new Error("فشل تحميل الملف المُصدَّر (" + r.status + ")");
// //                 return r.blob();
// //             });
// //     }

// //     function callOcrService(path, formData) {
// //         return fetch(OCR_SERVICE_URL + path, { method: "POST", body: formData })
// //             .then(function (r) {
// //                 if (!r.ok) {
// //                     return r.text().then(function (t) {
// //                         throw new Error("خدمة الـ OCR رفضت الطلب (" + r.status + "): " + (t || "").slice(0, 300));
// //                     });
// //                 }
// //                 return r.json();
// //             })
// //             .catch(function (err) {
// //                 if (err.message && err.message.indexOf("خدمة الـ OCR") === 0) throw err;
// //                 throw new Error("تعذر الاتصال بخدمة الـ OCR المحلية (تأكد إن السيرفر شغال على " + OCR_SERVICE_URL + ")");
// //             });
// //     }

// //     // ================= التنفيذ الفعلي =================

// //     if (typeof webAccessApi === "undefined" || !webAccessApi.getFocusedEntries) {
// //         alert("حدث خطأ: واجهة WebAccess غير متاحة في هذه الصفحة");
// //         return;
// //     }

// //     var entries;
// //     try {
// //         entries = webAccessApi.getFocusedEntries();
// //     } catch (e) {
// //         alert("تعذر قراءة المستند المحدد");
// //         return;
// //     }

// //     if (!entries || entries.length === 0) { alert("رجاء اختيار مستند أولاً"); return; }
// //     if (entries.length > 1) { alert("رجاء اختيار مستند واحد فقط"); return; }

// //     entryId = entries[0].id;

// //     if (window.__ocrRunningEntryId === entryId) return;
// //     window.__ocrRunningEntryId = entryId;
// //     if (btn) btn.classList.add("ocr-running");

// //     var fieldsById = {};
// //     var pageIds = [];

// //     showOverlayLoading("جاري قراءة بيانات القالب...");

// //     postJson("/laserfiche/MetadataService.ashx/GetMetadata", {
// //         repoName: repoName,
// //         entryIds: [String(entryId)],
// //         metadataFlags: 1
// //     })
// //     .then(function (metaResult) {
// //         if (!metaResult || !metaResult.d || !metaResult.d.Fields) {
// //             throw new Error("لا يمكن قراءة حقول القالب لهذا المستند (تأكد إن له قالب)");
// //         }
// //         (metaResult.d.Fields.templateFields || []).forEach(function (f) {
// //             fieldsById[f.name] = f.id;
// //         });
// //         return fetchPageIds();
// //     })
// //     .then(function (ids) {
// //         pageIds = ids || [];
// //         console.log("ArabicOCR: عدد صفحات المستند في Laserfiche =", pageIds.length);
// //         showOverlayLoading("جاري تصدير المستند...");
// //         return startExport();
// //     })
// //     .then(function (token) {
// //         showOverlayLoading("جاري تجهيز الصورة للتحليل...");
// //         return waitForExport(token).then(downloadExportedFile);
// //     })
// //     .then(function (pdfBlob) {
// //         if (!pdfBlob || pdfBlob.size === 0) {
// //             throw new Error("الملف المُصدَّر فارغ، تعذر المتابعة");
// //         }
// //         console.log("ArabicOCR: حجم الملف المُصدَّر =", pdfBlob.size, "بايت");

// //         showOverlayLoading("جاري تحليل المستند بالذكاء الاصطناعي...\nقد تستغرق العملية بعض الوقت، برجاء الانتظار.");

// //         var fieldsFormData = new FormData();
// //         fieldsFormData.append("image", pdfBlob, "page.pdf");
// //         fieldsFormData.append("fields", Object.keys(fieldsById).join(","));

// //         var allTextFormData = new FormData();
// //         allTextFormData.append("image", pdfBlob, "page.pdf");

// //         var extractFieldsPromise = callOcrService("/extract", fieldsFormData);

// //         // ⚠ الإصدار القديم كان بيبلع الخطأ هنا بـ console.warn وبيرجّع null،
// //         // فلما extract_all_text كان بيقع على السيرفر (AttributeError) المستخدم
// //         // كان بيشوف "تم بنجاح" والـ Text pane فاضي من غير أي أثر للمشكلة.
// //         var extractAllTextPromise = callOcrService("/extract-all-text", allTextFormData)
// //             .catch(function (err) {
// //                 textError = (err && err.message) || "خطأ غير معروف";
// //                 console.error("ArabicOCR: /extract-all-text فشل -", err);
// //                 return null;
// //             });

// //         return Promise.all([extractFieldsPromise, extractAllTextPromise]);
// //     })
// //     .then(function (results) {
// //         var extracted = results[0] || {};
// //         var allTextResult = results[1];

// //         if (allTextResult) {
// //             console.log("ArabicOCR: عدد الصفحات اللي وصلت للـ OCR =", allTextResult.page_count);
// //             // لو الرقم ده = 1 والمستند أكتر من صفحة، يبقى المشكلة في
// //             // EXPORT_PAGES_PARAM فوق مش في خدمة الـ OCR.
// //             if (allTextResult.page_count === 1 && pageIds.length > 1) {
// //                 textError = "التصدير رجّع صفحة واحدة بس والمستند " + pageIds.length +
// //                             " صفحات — راجع EXPORT_PAGES_PARAM في السكربت";
// //                 console.warn("ArabicOCR: " + textError);
// //             }
// //         }

// //         var fieldChanges = [];
// //         Object.keys(extracted).forEach(function (name) {
// //             if (fieldsById.hasOwnProperty(name) && extracted[name]) {
// //                 fieldChanges.push({
// //                     fieldId: fieldsById[name],
// //                     value: String(extracted[name]).trim(),
// //                     remove: false,
// //                     fieldIndex: 0
// //                 });
// //             }
// //         });

// //         var hasText = allTextResult && allTextResult.pages && allTextResult.pages.length;
// //         if (fieldChanges.length === 0 && !hasText) {
// //             showOverlayResult("لم يتم التعرف على أي حقول أو نص في هذا المستند", true, textError);
// //             return null;
// //         }

// //         showOverlayLoading("جاري حفظ البيانات في المستند...");

// //         return refreshSessionBeforeSave().then(function () {
// //             return postJson("/laserfiche/DocumentService.ashx/LockDocument", {
// //                 repoName: repoName,
// //                 documentId: entryId,
// //                 lockEfile: false,
// //                 autoCheckout: false
// //             });
// //         }).then(function () {
// //             documentWasLocked = true;
// //             return saveAllPagesText(pageIds, allTextResult ? allTextResult.pages : null);
// //         }).then(function () {
// //             if (fieldChanges.length === 0) {
// //                 return unlockDocument().then(function () { return { d: true }; });
// //             }
// //             return postJson("/laserfiche/DocumentService.ashx/SaveEntry", {
// //                 repoName: repoName,
// //                 documentId: entryId,
// //                 curPageNum: 0,
// //                 strCurPageId: 0,
// //                 changes: {
// //                     dirty: true,
// //                     newTemplateId: 0,
// //                     removeTemplate: false,
// //                     fieldChanges: fieldChanges,
// //                     tagChanges: [],
// //                     linkChanges: []
// //                 },
// //                 generalchanges: [],
// //                 annchanges: []
// //             }).then(function (saveResult) {
// //                 return unlockDocument().then(function () { return saveResult; });
// //             });
// //         });
// //     })
// //     .then(function (saveResult) {
// //         if (!saveResult) return;
// //         try { webAccessApi.refreshMetadata(); }
// //         catch (e) { console.warn("ArabicOCR: فشل تحديث الميتاداتا -", e); }
// //         try { webAccessApi.refreshContentsPane(); }
// //         catch (e) { console.warn("ArabicOCR: فشل تحديث Contents Pane -", e); }

// //         showOverlayResult(
// //             "تم استخراج البيانات وحفظها بنجاح ✔",
// //             false,
// //             textError ? "⚠ ملاحظة على النص الكامل:\n" + textError : null
// //         );

// //         // لو فيه مشكلة في النص، منعملش reload تلقائي عشان المستخدم يقرا التحذير.
// //         if (!textError) {
// //             setTimeout(function () { location.reload(); }, 1500);
// //         }
// //     })
// //     .catch(function (err) {
// //         console.error("ArabicOCR Error:", err);
// //         unlockDocument().then(function () {
// //             showOverlayResult("حدث خطأ:\n" + (err && err.message ? err.message : "خطأ غير متوقع"), true);
// //         });
// //     });
// // };



// // ═══════════════════════════════════════════════════════════════════
// // ArabicOCR — نسخة "صفحة صفحة" (page-wise export)
// // لو الرقم ده مش ظاهر في الكونسول أول ما تدوس الزرار، يبقى المتصفح شغال
// // على نسخة قديمة كاشد — اعمل cache-bust للسكربت (Ctrl+Shift+R مش كفاية).
// // ═══════════════════════════════════════════════════════════════════
// window.ARABIC_OCR_VERSION = "2026-08-04-pagewise";

// window.runArabicOcrAction = function () {
//     console.log("%cArabicOCR " + window.ARABIC_OCR_VERSION, "color:#2b6cb0;font-weight:bold");

//     var OVERLAY_ID = "arabicOcrOverlay";
//     var BTN_ID = "customOcrButton";
//     var repoName = new URLSearchParams(window.location.search).get("repo") || "demo";
//     var OCR_SERVICE_URL = window.location.protocol + "//" + window.location.hostname + ":8001";
//     var documentWasLocked = false;
//     var entryId = null;
//     var textError = null;   // سبب فشل استخراج النص الكامل، لو حصل

//     // ملاحظة على الـ export: الباراميتر p في ExportDisplay.aspx هو *رقم
//     // الصفحة* (1-based)، مش مُحدِّد نطاق. أي قيمة بره النطاق بترجّع:
//     //   "Specified argument was out of the range... Parameter name: pageNumber"
//     // فمفيش قيمة تجيب كل الصفحات مرة واحدة - لازم نلف صفحة صفحة.
//     var MAX_PAGES_GUARD = 50;   // حارس ضد اللوب اللانهائي

//     // ---------- Overlay UI ----------
//     function ensureOverlayStyles() {
//         if (document.getElementById("arabicOcrOverlayStyles")) return;
//         var style = document.createElement("style");
//         style.id = "arabicOcrOverlayStyles";
//         style.innerHTML =
//             "#" + OVERLAY_ID + "{position:fixed;top:0;left:0;width:100%;height:100%;" +
//             "background:rgba(0,0,0,0.55);z-index:2147483647;display:flex;" +
//             "align-items:center;justify-content:center;font-family:Tahoma,Arial,sans-serif;}" +
//             "#" + OVERLAY_ID + " .aoBox{background:#fff;border-radius:10px;padding:28px 32px;" +
//             "min-width:280px;max-width:420px;text-align:center;box-shadow:0 6px 24px rgba(0,0,0,0.3);direction:rtl;}" +
//             "#" + OVERLAY_ID + " .aoSpinner{width:42px;height:42px;margin:0 auto 16px;" +
//             "border:4px solid #ddd;border-top-color:#2b6cb0;border-radius:50%;" +
//             "animation:aoSpin 0.9s linear infinite;}" +
//             "@keyframes aoSpin{to{transform:rotate(360deg);}}" +
//             "#" + OVERLAY_ID + " .aoMsg{font-size:15px;color:#222;margin-bottom:4px;white-space:pre-line;}" +
//             "#" + OVERLAY_ID + " .aoIcon{font-size:38px;margin-bottom:10px;}" +
//             "#" + OVERLAY_ID + " .aoClose{margin-top:16px;padding:8px 22px;border:none;" +
//             "border-radius:6px;background:#2b6cb0;color:#fff;font-size:14px;cursor:pointer;}" +
//             "#" + OVERLAY_ID + " .aoClose.error{background:#c53030;}" +
//             "#" + OVERLAY_ID + " .aoWarn{margin-top:10px;font-size:13px;color:#b7791f;" +
//             "white-space:pre-line;direction:rtl;}";
//         document.head.appendChild(style);
//     }

//     function getOverlayEl() {
//         var overlay = document.getElementById(OVERLAY_ID);
//         if (!overlay) {
//             overlay = document.createElement("div");
//             overlay.id = OVERLAY_ID;
//             document.body.appendChild(overlay);
//         }
//         return overlay;
//     }

//     function showOverlayLoading(message) {
//         ensureOverlayStyles();
//         getOverlayEl().innerHTML =
//             '<div class="aoBox"><div class="aoSpinner"></div><div class="aoMsg">' +
//             message + "</div></div>";
//     }

//     function showOverlayResult(message, isError, warning) {
//         ensureOverlayStyles();
//         var overlay = getOverlayEl();
//         var icon = isError ? "\u26A0\uFE0F" : "\u2705";
//         overlay.innerHTML =
//             '<div class="aoBox"><div class="aoIcon">' + icon + '</div><div class="aoMsg">' +
//             message + '</div>' +
//             (warning ? '<div class="aoWarn">' + warning + '</div>' : '') +
//             '<button class="aoClose' + (isError ? " error" : "") +
//             '" id="aoCloseBtn">تم</button></div>';
//         document.getElementById("aoCloseBtn").onclick = hideOverlay;
//         unlockButton();
//     }

//     function hideOverlay() {
//         var overlay = document.getElementById(OVERLAY_ID);
//         if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
//     }

//     // ---------- منع الضغط المزدوج (مربوط بالمستند الحالي فقط) ----------
//     var btn = document.getElementById(BTN_ID);

//     function unlockButton() {
//         window.__ocrRunningEntryId = null;
//         if (btn) btn.classList.remove("ocr-running");
//     }

//     // ---------- Helpers ----------
//     function getXsrfToken() {
//         var match = document.cookie.match(/(?:^|;\s*)XSRF-TOKEN=([^;]*)/);
//         return match ? decodeURIComponent(match[1]) : "";
//     }

//     function postJson(url, body) {
//         return fetch(url, {
//             method: "POST",
//             credentials: "same-origin",
//             headers: {
//                 "Content-Type": "application/json;charset=UTF-8",
//                 "Lf-Repository": repoName,
//                 "X-Lf-Repo-ID": repoName,
//                 "X-XSRF-TOKEN": getXsrfToken()
//             },
//             body: JSON.stringify(body)
//         }).then(function (r) {
//             if (!r.ok) throw new Error("طلب الشبكة فشل (" + r.status + "): " + url);
//             return r.json();
//         });
//     }

//     function sleep(ms) {
//         return new Promise(function (resolve) { setTimeout(resolve, ms); });
//     }

//     // ================= الحصول على معرّفات كل الصفحات =================
//     //
//     // الإصدار القديم كان بياخد pageId واحد بس (الصفحة المعروضة) من resource
//     // timing، وبيكتب نص المستند كله فيه. يعني حتى لو الـ OCR رجّع 5 صفحات،
//     // الخمسة كانوا بيتلزقوا في صفحة 1 والباقي بيفضل فاضي.

//     function scrapePageIdsFromResourceTiming() {
//         // الصفحات اللي اتعرضت (أو اتحمّلت الـ thumbnails بتاعتها) بتسيب
//         // أثرها في resource timing. مش مضمون إنها كل الصفحات - ده fallback.
//         var ids = [];
//         try {
//             var resources = performance.getEntriesByType("resource");
//             for (var i = 0; i < resources.length; i++) {
//                 var url = resources[i].name;
//                 if (url.indexOf("documentId=" + entryId) === -1 &&
//                     url.indexOf("docId=" + entryId) === -1) continue;
//                 if (url.indexOf("TileData.aspx") === -1 &&
//                     url.indexOf("Thumbnail") === -1) continue;
//                 var m = url.match(/[?&]pageId=([^&]+)/);
//                 if (m && ids.indexOf(m[1]) === -1) ids.push(m[1]);
//             }
//         } catch (e) {
//             console.warn("ArabicOCR: تعذر قراءة pageIds من resource timing -", e);
//         }
//         return ids;
//     }

//     function fetchPageIds() {
//         // ❌ الأربع endpoints اللي كانوا هنا (GetDocumentInfo / GetDocInfo /
//         // GetPages / GetPageInfo) كلهم رجّعوا 500 "Unknown Error" في الـ HAR
//         // — يعني مش موجودين في نسختك من Web Access. اتشالوا.
//         //
//         // البديل: resource timing. الصفحة المعروضة وكل thumbnail اتحمّل
//         // بيسيبوا URL فيه pageId. عشان يطلعوا كلهم، لازم بانل الـ Thumbnails
//         // يكون مفتوح (وهو مفتوح عندك في الشاشة).
//         var ids = scrapePageIdsFromResourceTiming();
//         if (!ids.length) {
//             console.warn(
//                 "ArabicOCR: مفيش أي pageId في resource timing. افتح بانل " +
//                 "الـ Thumbnails ونزّل لآخره، وبعدين شغّل الزرار تاني.\n" +
//                 "لاستكشاف الشكل الحقيقي للـ URLs شغّل: __ocrDumpPageUrls()"
//             );
//         }
//         return Promise.resolve(ids);
//     }

//     // أداة تشخيص: بتطبع كل الـ URLs اللي فيها pageId عشان تعرف مين بيخدم
//     // الصفحات في نسختك وتبني عليه. شغّلها من الـ console.
//     window.__ocrDumpPageUrls = function () {
//         var urls = performance.getEntriesByType("resource")
//             .map(function (r) { return r.name; })
//             .filter(function (n) { return /pageId=/i.test(n); });
//         console.table(urls);
//         return urls;
//     };

//     function saveAllPagesText(ids, texts) {
//         if (!texts || !texts.length) return Promise.resolve();
//         if (!ids || !ids.length) {
//             textError = "تعذر الحصول على معرّفات صفحات المستند - شغّل __ocrDumpPageUrls() في الكونسول";
//             return Promise.resolve();
//         }
//         if (ids.length !== texts.length) {
//             textError = "عدد pageIds (" + ids.length + ") لا يطابق عدد الصفحات المستخرجة (" + texts.length + ")";
//             console.warn("ArabicOCR: " + textError);
//         }

//         var count = Math.min(ids.length, texts.length);
//         var chain = Promise.resolve();
//         for (var i = 0; i < count; i++) {
//             (function (idx) {
//                 chain = chain.then(function () {
//                     if (!texts[idx]) return null;
//                     return postJson("/laserfiche/DocumentService.ashx/SetTextByDocIdAndPageId", {
//                         repoName: repoName,
//                         documentId: entryId,
//                         strPageId: String(ids[idx]),
//                         newText: texts[idx],
//                         hints: []
//                     });
//                 });
//             })(i);
//         }
//         return chain.catch(function (err) {
//             textError = "فشل حفظ نص إحدى الصفحات: " + (err && err.message);
//             console.warn("ArabicOCR: " + textError);
//         });
//     }

//     function refreshSessionBeforeSave() {
//         return postJson("/laserfiche/MetadataService.ashx/GetMetadata", {
//             repoName: repoName,
//             entryIds: [String(entryId)],
//             metadataFlags: 1
//         }).catch(function (err) {
//             console.warn("ArabicOCR: فشل تجديد الجلسة قبل الحفظ -", err);
//         });
//     }

//     function unlockDocument() {
//         if (!documentWasLocked) return Promise.resolve();
//         return postJson("/laserfiche/DocumentService.ashx/UnlockDocument", {
//             repoName: repoName,
//             documentId: entryId
//         }).then(function (result) {
//             documentWasLocked = false;
//             return result;
//         }).catch(function (err) {
//             console.warn("ArabicOCR: فشل فك القفل عن المستند -", err);
//         });
//     }

//     function startExport(pageNumber) {
//         var url = "/laserfiche/Dialogs/Export/ExportDisplay.aspx"
//             + "?r=" + encodeURIComponent(repoName)
//             + "&t=1&i=" + entryId + "&v=0&p=" + pageNumber
//             + "&f=3&optToken=&sh=&loc=0&sep=&reportFormat=&e=";
//         return fetch(url, { credentials: "same-origin" })
//             .then(function (r) {
//                 if (!r.ok) throw new Error("فشل بدء عملية التصدير (" + r.status + ")");
//                 return r.text();
//             })
//             .then(function (html) {
//                 var m = html.match(/exportToken&quot;:&quot;([a-f0-9-]+)&quot;/i)
//                       || html.match(/"exportToken"\s*:\s*"([a-f0-9-]+)"/i);
//                 if (!m) throw new Error("تعذر الحصول على exportToken");
//                 return m[1];
//             });
//     }

//     function waitForExport(token) {
//         var attempts = 0;
//         function check() {
//             attempts++;
//             if (attempts > 40) throw new Error("انتهت مهلة انتظار التصدير (Timeout)");
//             return postJson("/laserfiche/ExportService.ashx/GetExportStatus", {
//                 repoName: repoName,
//                 token: token
//             }).then(function (statusResult) {
//                 var s = statusResult.d;
//                 if (!s) throw new Error("استجابة غير متوقعة أثناء التصدير");
//                 if (s.State === 2 || s.Completion === 100) return token;
//                 if (s.FailMsg) {
//                     var failure = new Error("فشل التصدير: " + s.FailMsg);
//                     // ده الخطأ اللي Laserfiche بيرجّعه لما رقم الصفحة يتعدى
//                     // عدد صفحات المستند - يعني "خلصنا"، مش عطل حقيقي.
//                     failure.isPageOutOfRange = /pageNumber/i.test(s.FailMsg);
//                     throw failure;
//                 }
//                 return sleep(500).then(check);
//             });
//         }
//         return check();
//     }

//     function exportSinglePage(pageNumber) {
//         return startExport(pageNumber)
//             .then(waitForExport)
//             .then(downloadExportedFile);
//     }

//     function exportAllPages(onProgress) {
//         // بنلف من صفحة 1 لحد ما Laserfiche يقول "pageNumber بره النطاق".
//         // مش بنحتاج نعرف عدد الصفحات مقدمًا - المستند نفسه بيقولنا فين النهاية،
//         // وده أأمن من قراءة العدد من الـ DOM أو من endpoint مش موجود.
//         var blobs = [];

//         function next(pageNumber) {
//             if (pageNumber > MAX_PAGES_GUARD) {
//                 console.warn("ArabicOCR: وقفت عند حارس " + MAX_PAGES_GUARD + " صفحة.");
//                 return Promise.resolve(blobs);
//             }
//             if (onProgress) onProgress(pageNumber);
//             return exportSinglePage(pageNumber).then(function (blob) {
//                 if (!blob || blob.size === 0) return blobs;
//                 blobs.push(blob);
//                 return next(pageNumber + 1);
//             }).catch(function (err) {
//                 if (err && err.isPageOutOfRange) {
//                     // النهاية الطبيعية للمستند
//                     return blobs;
//                 }
//                 if (blobs.length) {
//                     console.warn("ArabicOCR: فشل تصدير صفحة " + pageNumber +
//                                  "، هنكمل باللي اتصدّر (" + blobs.length + " صفحة) -", err);
//                     return blobs;
//                 }
//                 throw err;   // فشل من أول صفحة = عطل حقيقي
//             });
//         }

//         return next(1);
//     }

//     function downloadExportedFile(token) {
//         var url = "/laserfiche/Dialogs/Export/GetExportFile.aspx?token="
//             + encodeURIComponent(token) + "&repo=" + encodeURIComponent(repoName);
//         return fetch(url, { credentials: "same-origin" })
//             .then(function (r) {
//                 if (!r.ok) throw new Error("فشل تحميل الملف المُصدَّر (" + r.status + ")");
//                 return r.blob();
//             });
//     }

//     function callOcrService(path, formData) {
//         return fetch(OCR_SERVICE_URL + path, { method: "POST", body: formData })
//             .then(function (r) {
//                 if (!r.ok) {
//                     return r.text().then(function (t) {
//                         throw new Error("خدمة الـ OCR رفضت الطلب (" + r.status + "): " + (t || "").slice(0, 300));
//                     });
//                 }
//                 return r.json();
//             })
//             .catch(function (err) {
//                 if (err.message && err.message.indexOf("خدمة الـ OCR") === 0) throw err;
//                 throw new Error("تعذر الاتصال بخدمة الـ OCR المحلية (تأكد إن السيرفر شغال على " + OCR_SERVICE_URL + ")");
//             });
//     }

//     function mergeFields(target, source) {
//         Object.keys(source || {}).forEach(function (key) {
//             var value = source[key];
//             var current = target[key];
//             if (value !== null && value !== "" && value !== undefined &&
//                 (current === null || current === "" || current === undefined)) {
//                 target[key] = value;
//             }
//         });
//         return target;
//     }

//     function processPages(pageBlobs, fieldNames) {
//         // كل صفحة بتتبعت لوحدها لأن الـ export مبيرجّعش أكتر من صفحة في PDF واحد.
//         // النص: كل صفحة بترجّع نصها وبيتكتب في pageId بتاعها.
//         // الحقول: بنمشي بالترتيب وندمج (أول قيمة غير فاضية بتكسب)، وبنبطّل
//         // نداءات الحقول أول ما كل الحقول تتملى - نفس منطق merge_page_fields
//         // على السيرفر، عشان منستهلكش نداء Ollama من غير داعي.
//         var merged = {};
//         var texts = [];
//         var chain = Promise.resolve();

//         pageBlobs.forEach(function (blob, index) {
//             chain = chain.then(function () {
//                 showOverlayLoading(
//                     "جاري تحليل صفحة " + (index + 1) + " من " + pageBlobs.length +
//                     " بالذكاء الاصطناعي...\nقد تستغرق العملية بعض الوقت، برجاء الانتظار."
//                 );

//                 var textForm = new FormData();
//                 textForm.append("image", blob, "page" + (index + 1) + ".pdf");
//                 var textPromise = callOcrService("/extract-all-text", textForm)
//                     .then(function (result) { return (result && result.text) || ""; })
//                     .catch(function (err) {
//                         textError = (err && err.message) || "خطأ غير معروف";
//                         console.error("ArabicOCR: /extract-all-text فشل في صفحة " + (index + 1), err);
//                         return "";
//                     });

//                 var stillMissing = fieldNames.some(function (name) {
//                     var v = merged[name];
//                     return v === null || v === "" || v === undefined;
//                 });

//                 var fieldsPromise = Promise.resolve(null);
//                 if (fieldNames.length && stillMissing) {
//                     var fieldsForm = new FormData();
//                     fieldsForm.append("image", blob, "page" + (index + 1) + ".pdf");
//                     fieldsForm.append("fields", fieldNames.join(","));
//                     fieldsPromise = callOcrService("/extract", fieldsForm).catch(function (err) {
//                         console.error("ArabicOCR: /extract فشل في صفحة " + (index + 1), err);
//                         return null;
//                     });
//                 }

//                 return Promise.all([textPromise, fieldsPromise]).then(function (results) {
//                     texts.push(results[0]);
//                     mergeFields(merged, results[1]);
//                 });
//             });
//         });

//         return chain.then(function () {
//             return { fields: merged, texts: texts };
//         });
//     }

//     // ================= التنفيذ الفعلي =================

//     if (typeof webAccessApi === "undefined" || !webAccessApi.getFocusedEntries) {
//         alert("حدث خطأ: واجهة WebAccess غير متاحة في هذه الصفحة");
//         return;
//     }

//     var entries;
//     try {
//         entries = webAccessApi.getFocusedEntries();
//     } catch (e) {
//         alert("تعذر قراءة المستند المحدد");
//         return;
//     }

//     if (!entries || entries.length === 0) { alert("رجاء اختيار مستند أولاً"); return; }
//     if (entries.length > 1) { alert("رجاء اختيار مستند واحد فقط"); return; }

//     entryId = entries[0].id;

//     if (window.__ocrRunningEntryId === entryId) return;
//     window.__ocrRunningEntryId = entryId;
//     if (btn) btn.classList.add("ocr-running");

//     var fieldsById = {};
//     var pageIds = [];
//     var pageTexts = [];

//     showOverlayLoading("جاري قراءة بيانات القالب...");

//     postJson("/laserfiche/MetadataService.ashx/GetMetadata", {
//         repoName: repoName,
//         entryIds: [String(entryId)],
//         metadataFlags: 1
//     })
//     .then(function (metaResult) {
//         if (!metaResult || !metaResult.d || !metaResult.d.Fields) {
//             throw new Error("لا يمكن قراءة حقول القالب لهذا المستند (تأكد إن له قالب)");
//         }
//         (metaResult.d.Fields.templateFields || []).forEach(function (f) {
//             fieldsById[f.name] = f.id;
//         });
//         return fetchPageIds();
//     })
//     .then(function (ids) {
//         pageIds = ids || [];
//         console.log("ArabicOCR: pageIds من resource timing =", pageIds);
//         showOverlayLoading("جاري تصدير المستند...");
//         return exportAllPages(function (pageNumber) {
//             showOverlayLoading("جاري تصدير صفحة " + pageNumber + "...");
//         });
//     })
//     .then(function (pageBlobs) {
//         if (!pageBlobs.length) throw new Error("لم يتم تصدير أي صفحة من المستند");
//         console.log("ArabicOCR: اتصدّر " + pageBlobs.length + " صفحة");

//         if (pageIds.length && pageIds.length !== pageBlobs.length) {
//             console.warn(
//                 "ArabicOCR: المستند " + pageBlobs.length + " صفحة بس عندنا " +
//                 pageIds.length + " pageId. افتح بانل الـ Thumbnails ونزّل لآخره " +
//                 "قبل ما تضغط الزرار، عشان كل الصفحات تسيب أثرها في resource timing."
//             );
//         }

//         return processPages(pageBlobs, Object.keys(fieldsById));
//     })
//     .then(function (processed) {
//         var extracted = processed.fields || {};
//         pageTexts = processed.texts || [];

//         var fieldChanges = [];
//         Object.keys(extracted).forEach(function (name) {
//             if (fieldsById.hasOwnProperty(name) && extracted[name]) {
//                 fieldChanges.push({
//                     fieldId: fieldsById[name],
//                     value: String(extracted[name]).trim(),
//                     remove: false,
//                     fieldIndex: 0
//                 });
//             }
//         });

//         var hasText = pageTexts.some(function (t) { return t && t.length; });
//         if (fieldChanges.length === 0 && !hasText) {
//             showOverlayResult("لم يتم التعرف على أي حقول أو نص في هذا المستند", true, textError);
//             return null;
//         }

//         showOverlayLoading("جاري حفظ البيانات في المستند...");

//         return refreshSessionBeforeSave().then(function () {
//             return postJson("/laserfiche/DocumentService.ashx/LockDocument", {
//                 repoName: repoName,
//                 documentId: entryId,
//                 lockEfile: false,
//                 autoCheckout: false
//             });
//         }).then(function () {
//             documentWasLocked = true;
//             return saveAllPagesText(pageIds, pageTexts);
//         }).then(function () {
//             if (fieldChanges.length === 0) {
//                 return unlockDocument().then(function () { return { d: true }; });
//             }
//             return postJson("/laserfiche/DocumentService.ashx/SaveEntry", {
//                 repoName: repoName,
//                 documentId: entryId,
//                 curPageNum: 0,
//                 strCurPageId: 0,
//                 changes: {
//                     dirty: true,
//                     newTemplateId: 0,
//                     removeTemplate: false,
//                     fieldChanges: fieldChanges,
//                     tagChanges: [],
//                     linkChanges: []
//                 },
//                 generalchanges: [],
//                 annchanges: []
//             }).then(function (saveResult) {
//                 return unlockDocument().then(function () { return saveResult; });
//             });
//         });
//     })
//     .then(function (saveResult) {
//         if (!saveResult) return;
//         try { webAccessApi.refreshMetadata(); }
//         catch (e) { console.warn("ArabicOCR: فشل تحديث الميتاداتا -", e); }
//         try { webAccessApi.refreshContentsPane(); }
//         catch (e) { console.warn("ArabicOCR: فشل تحديث Contents Pane -", e); }

//         showOverlayResult(
//             "تم استخراج البيانات وحفظها بنجاح ✔",
//             false,
//             textError ? "⚠ ملاحظة على النص الكامل:\n" + textError : null
//         );

//         // لو فيه مشكلة في النص، منعملش reload تلقائي عشان المستخدم يقرا التحذير.
//         if (!textError) {
//             setTimeout(function () { location.reload(); }, 1500);
//         }
//     })
//     .catch(function (err) {
//         console.error("ArabicOCR Error:", err);
//         unlockDocument().then(function () {
//             showOverlayResult("حدث خطأ:\n" + (err && err.message ? err.message : "خطأ غير متوقع"), true);
//         });
//     });
// };


// ═══════════════════════════════════════════════════════════════════
// ArabicOCR — نسخة "تصدير متوازٍ" (parallel-export)
// كل الصفحات بتتصدّر في نفس الوقت → وقت التصدير = وقت صفحة واحدة.
// الـ OCR بيشتغل صفحة ورا صفحة (Ollama مش بيقبل تعدد حقيقي).
// ═══════════════════════════════════════════════════════════════════
window.ARABIC_OCR_VERSION = "2026-08-04-parallelexport";

window.runArabicOcrAction = function () {
    console.log("%cArabicOCR " + window.ARABIC_OCR_VERSION, "color:#2b6cb0;font-weight:bold");

    var OVERLAY_ID = "arabicOcrOverlay";
    var BTN_ID     = "customOcrButton";
    var repoName   = new URLSearchParams(window.location.search).get("repo") || "demo";
    var OCR_SERVICE_URL = window.location.protocol + "//" + window.location.hostname + ":8001";
    var documentWasLocked = false;
    var entryId   = null;
    var textError = null;

    // حارس ضد اللوب اللانهائي لو resource timing ما رجعتش pageIds
    var MAX_PAGES_GUARD = 50;

    // ---------- Overlay UI ----------
    function ensureOverlayStyles() {
        if (document.getElementById("arabicOcrOverlayStyles")) return;
        var style = document.createElement("style");
        style.id = "arabicOcrOverlayStyles";
        style.innerHTML =
            "#" + OVERLAY_ID + "{position:fixed;top:0;left:0;width:100%;height:100%;" +
            "background:rgba(0,0,0,0.55);z-index:2147483647;display:flex;" +
            "align-items:center;justify-content:center;font-family:Tahoma,Arial,sans-serif;}" +
            "#" + OVERLAY_ID + " .aoBox{background:#fff;border-radius:10px;padding:28px 32px;" +
            "min-width:280px;max-width:420px;text-align:center;box-shadow:0 6px 24px rgba(0,0,0,0.3);direction:rtl;}" +
            "#" + OVERLAY_ID + " .aoSpinner{width:42px;height:42px;margin:0 auto 16px;" +
            "border:4px solid #ddd;border-top-color:#2b6cb0;border-radius:50%;" +
            "animation:aoSpin 0.9s linear infinite;}" +
            "@keyframes aoSpin{to{transform:rotate(360deg);}}" +
            "#" + OVERLAY_ID + " .aoMsg{font-size:15px;color:#222;margin-bottom:4px;white-space:pre-line;}" +
            "#" + OVERLAY_ID + " .aoIcon{font-size:38px;margin-bottom:10px;}" +
            "#" + OVERLAY_ID + " .aoClose{margin-top:16px;padding:8px 22px;border:none;" +
            "border-radius:6px;background:#2b6cb0;color:#fff;font-size:14px;cursor:pointer;}" +
            "#" + OVERLAY_ID + " .aoClose.error{background:#c53030;}" +
            "#" + OVERLAY_ID + " .aoWarn{margin-top:10px;font-size:13px;color:#b7791f;" +
            "white-space:pre-line;direction:rtl;}";
        document.head.appendChild(style);
    }

    function getOverlayEl() {
        var el = document.getElementById(OVERLAY_ID);
        if (!el) {
            el = document.createElement("div");
            el.id = OVERLAY_ID;
            document.body.appendChild(el);
        }
        return el;
    }

    function showOverlayLoading(msg) {
        ensureOverlayStyles();
        getOverlayEl().innerHTML =
            '<div class="aoBox"><div class="aoSpinner"></div><div class="aoMsg">' +
            msg + "</div></div>";
    }

    function showOverlayResult(msg, isError, warning) {
        ensureOverlayStyles();
        var icon = isError ? "\u26A0\uFE0F" : "\u2705";
        getOverlayEl().innerHTML =
            '<div class="aoBox"><div class="aoIcon">' + icon + '</div>' +
            '<div class="aoMsg">' + msg + '</div>' +
            (warning ? '<div class="aoWarn">' + warning + '</div>' : '') +
            '<button class="aoClose' + (isError ? " error" : "") +
            '" id="aoCloseBtn">تم</button></div>';
        document.getElementById("aoCloseBtn").onclick = hideOverlay;
        unlockButton();
    }

    function hideOverlay() {
        var el = document.getElementById(OVERLAY_ID);
        if (el && el.parentNode) el.parentNode.removeChild(el);
    }

    var btn = document.getElementById(BTN_ID);
    function unlockButton() {
        window.__ocrRunningEntryId = null;
        if (btn) btn.classList.remove("ocr-running");
    }

    // ---------- Helpers ----------
    function getXsrfToken() {
        var m = document.cookie.match(/(?:^|;\s*)XSRF-TOKEN=([^;]*)/);
        return m ? decodeURIComponent(m[1]) : "";
    }

    function postJson(url, body) {
        return fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json;charset=UTF-8",
                "Lf-Repository": repoName,
                "X-Lf-Repo-ID": repoName,
                "X-XSRF-TOKEN": getXsrfToken()
            },
            body: JSON.stringify(body)
        }).then(function (r) {
            if (!r.ok) throw new Error("طلب الشبكة فشل (" + r.status + "): " + url);
            return r.json();
        });
    }

    function sleep(ms) {
        return new Promise(function (res) { setTimeout(res, ms); });
    }

    // ---------- pageIds من resource timing ----------
    // افتح بانل الـ Thumbnails ونزّل لآخره قبل الضغط عشان كل الصفحات تسجّل.
    // أداة تشخيص: window.__ocrDumpPageUrls()
    function fetchPageIds() {
        var ids = [];
        try {
            performance.getEntriesByType("resource").forEach(function (r) {
                var u = r.name;
                if ((u.indexOf("documentId=" + entryId) === -1 &&
                     u.indexOf("docId="       + entryId) === -1)) return;
                if (u.indexOf("TileData.aspx") === -1 &&
                    u.indexOf("Thumbnail")     === -1)  return;
                var m = u.match(/[?&]pageId=([^&]+)/);
                if (m && ids.indexOf(m[1]) === -1) ids.push(m[1]);
            });
        } catch (e) {
            console.warn("ArabicOCR: تعذر قراءة pageIds -", e);
        }
        if (ids.length) {
            console.log("ArabicOCR: pageIds من resource timing =", ids);
        } else {
            console.warn(
                "ArabicOCR: مفيش pageIds — افتح بانل Thumbnails ونزّل لآخره. " +
                "لاستكشاف الـ URLs: window.__ocrDumpPageUrls()"
            );
        }
        return ids;
    }

    window.__ocrDumpPageUrls = function () {
        var urls = performance.getEntriesByType("resource")
            .map(function (r) { return r.name; })
            .filter(function (n) { return /pageId=/i.test(n); });
        console.table(urls);
        return urls;
    };

    // ---------- Export helpers ----------
    function startExport(pageNum) {
        var url = "/laserfiche/Dialogs/Export/ExportDisplay.aspx"
            + "?r=" + encodeURIComponent(repoName)
            + "&t=1&i=" + entryId + "&v=0&p=" + pageNum
            + "&f=3&optToken=&sh=&loc=0&sep=&reportFormat=&e=";
        return fetch(url, { credentials: "same-origin" })
            .then(function (r) {
                if (!r.ok) throw new Error("فشل بدء التصدير (" + r.status + ")");
                return r.text();
            })
            .then(function (html) {
                var m = html.match(/exportToken&quot;:&quot;([a-f0-9-]+)&quot;/i)
                      || html.match(/"exportToken"\s*:\s*"([a-f0-9-]+)"/i);
                if (!m) throw new Error("تعذر الحصول على exportToken");
                return m[1];
            });
    }

    function waitForExport(token) {
        var attempts = 0;
        function check() {
            if (++attempts > 60) throw new Error("انتهت مهلة انتظار التصدير");
            return postJson("/laserfiche/ExportService.ashx/GetExportStatus", {
                repoName: repoName, token: token
            }).then(function (res) {
                var s = res.d;
                if (!s) throw new Error("استجابة غير متوقعة أثناء التصدير");
                if (s.State === 2 || s.Completion === 100) return token;
                if (s.FailMsg) {
                    var err = new Error("فشل التصدير: " + s.FailMsg);
                    err.isPageOutOfRange = /pageNumber/i.test(s.FailMsg);
                    throw err;
                }
                return sleep(500).then(check);
            });
        }
        return check();
    }

    function downloadBlob(token) {
        return fetch(
            "/laserfiche/Dialogs/Export/GetExportFile.aspx?token=" +
            encodeURIComponent(token) + "&repo=" + encodeURIComponent(repoName),
            { credentials: "same-origin" }
        ).then(function (r) {
            if (!r.ok) throw new Error("فشل تحميل الملف (" + r.status + ")");
            return r.blob();
        });
    }

    // تصدير صفحة واحدة (export → poll → download)
    function exportOnePage(pageNum) {
        return startExport(pageNum)
            .then(waitForExport)
            .then(downloadBlob);
    }

    // ═══════════════════════════════════════════════════════════════
    // التصدير المتوازي — القلب الجديد
    // ═══════════════════════════════════════════════════════════════
    // لو عندنا عدد الصفحات من resource timing: نطلق كل الـ exports في نفس
    // الوقت بـ Promise.all فوقت التصدير = وقت أبطأ صفحة واحدة.
    //
    // لو ما عرفناش العدد: نلف صفحة صفحة (fallback) لأن مش عندنا طريقة
    // تانية نعرف فين المستند خلص.

    function exportAllParallel(knownCount) {
        showOverlayLoading("جاري تصدير " + knownCount + " صفحة بالتوازي...");
        var promises = [];
        for (var p = 1; p <= knownCount; p++) {
            promises.push(exportOnePage(p).catch(function (err) {
                // صفحة خارج النطاق أو فاضية نتجاهلها
                if (err && err.isPageOutOfRange) return null;
                console.warn("ArabicOCR: فشل تصدير صفحة -", err);
                return null;
            }));
        }
        return Promise.all(promises).then(function (blobs) {
            return blobs.filter(function (b) { return b && b.size > 0; });
        });
    }

    function exportAllSequential() {
        // Fallback: نلف ونكتشف نهاية المستند من الـ error
        var blobs = [];
        function next(p) {
            if (p > MAX_PAGES_GUARD) return Promise.resolve(blobs);
            showOverlayLoading("جاري تصدير صفحة " + p + "...");
            return exportOnePage(p).then(function (blob) {
                if (!blob || blob.size === 0) return blobs;
                blobs.push(blob);
                return next(p + 1);
            }).catch(function (err) {
                if (err && err.isPageOutOfRange) return blobs;
                if (blobs.length) {
                    console.warn("ArabicOCR: توقف عند صفحة " + p + " -", err);
                    return blobs;
                }
                throw err;
            });
        }
        return next(1);
    }

    // ---------- OCR helpers ----------
    function callOcr(path, formData) {
        return fetch(OCR_SERVICE_URL + path, { method: "POST", body: formData })
            .then(function (r) {
                if (!r.ok) {
                    return r.text().then(function (t) {
                        throw new Error("خدمة الـ OCR رفضت الطلب (" + r.status + "): " + (t || "").slice(0, 200));
                    });
                }
                return r.json();
            })
            .catch(function (err) {
                if (err.message && err.message.indexOf("خدمة الـ OCR") === 0) throw err;
                throw new Error("تعذر الاتصال بخدمة الـ OCR (تأكد إن السيرفر شغال: " + OCR_SERVICE_URL + ")");
            });
    }

    // معالجة الصفحات بـ OCR — النص والحقول بالتتابع لأن Ollama صف واحد
    function processPages(pageBlobs, fieldNames) {
        var texts  = [];
        var merged = {};
        var chain  = Promise.resolve();

        pageBlobs.forEach(function (blob, idx) {
            chain = chain.then(function () {
                showOverlayLoading(
                    "جاري تحليل صفحة " + (idx + 1) + " من " + pageBlobs.length +
                    " بالذكاء الاصطناعي...\nبرجاء الانتظار."
                );

                // نص الصفحة
                var textForm = new FormData();
                textForm.append("image", blob, "p" + (idx + 1) + ".pdf");
                var textP = callOcr("/extract-all-text", textForm)
                    .then(function (r) { return (r && r.text) || ""; })
                    .catch(function (err) {
                        textError = err && err.message;
                        console.error("ArabicOCR: text OCR فشل في صفحة " + (idx + 1), err);
                        return "";
                    });

                // حقول الصفحة (بس لو لسه فيه حقول ناقصة)
                var needFields = fieldNames.length && fieldNames.some(function (n) {
                    var v = merged[n];
                    return v === null || v === "" || v === undefined;
                });
                var fieldsP = Promise.resolve(null);
                if (needFields) {
                    var fForm = new FormData();
                    fForm.append("image", blob, "p" + (idx + 1) + ".pdf");
                    fForm.append("fields", fieldNames.join(","));
                    fieldsP = callOcr("/extract", fForm).catch(function (err) {
                        console.error("ArabicOCR: fields OCR فشل في صفحة " + (idx + 1), err);
                        return null;
                    });
                }

                return Promise.all([textP, fieldsP]).then(function (res) {
                    texts.push(res[0]);
                    // merge: أول قيمة غير فاضية بتكسب
                    var pageFields = res[1] || {};
                    Object.keys(pageFields).forEach(function (k) {
                        var v = pageFields[k];
                        if (v !== null && v !== "" && v !== undefined) {
                            var cur = merged[k];
                            if (cur === null || cur === "" || cur === undefined)
                                merged[k] = v;
                        }
                    });
                });
            });
        });

        return chain.then(function () { return { fields: merged, texts: texts }; });
    }

    // ---------- حفظ نص كل صفحة ----------
    function saveAllPagesText(pageIds, texts) {
        if (!texts || !texts.length) return Promise.resolve();
        if (!pageIds || !pageIds.length) {
            textError = "تعذر الحصول على pageIds — افتح بانل Thumbnails ونزّل لآخره";
            console.warn("ArabicOCR: " + textError);
            return Promise.resolve();
        }
        if (pageIds.length !== texts.length) {
            console.warn("ArabicOCR: pageIds (" + pageIds.length + ") ≠ صفحات OCR (" + texts.length + ")");
        }
        var count = Math.min(pageIds.length, texts.length);
        var chain = Promise.resolve();
        for (var i = 0; i < count; i++) {
            (function (idx) {
                chain = chain.then(function () {
                    if (!texts[idx]) return null;
                    return postJson("/laserfiche/DocumentService.ashx/SetTextByDocIdAndPageId", {
                        repoName: repoName,
                        documentId: entryId,
                        strPageId: String(pageIds[idx]),
                        newText: texts[idx],
                        hints: []
                    });
                });
            })(i);
        }
        return chain.catch(function (err) {
            textError = "فشل حفظ نص إحدى الصفحات: " + (err && err.message);
            console.warn("ArabicOCR: " + textError);
        });
    }

    function refreshSession() {
        return postJson("/laserfiche/MetadataService.ashx/GetMetadata", {
            repoName: repoName, entryIds: [String(entryId)], metadataFlags: 1
        }).catch(function (err) {
            console.warn("ArabicOCR: فشل تجديد الجلسة -", err);
        });
    }

    function unlockDocument() {
        if (!documentWasLocked) return Promise.resolve();
        return postJson("/laserfiche/DocumentService.ashx/UnlockDocument", {
            repoName: repoName, documentId: entryId
        }).then(function (r) {
            documentWasLocked = false; return r;
        }).catch(function (err) {
            console.warn("ArabicOCR: فشل فك القفل -", err);
        });
    }

    // ================= التنفيذ الفعلي =================

    if (typeof webAccessApi === "undefined" || !webAccessApi.getFocusedEntries) {
        alert("حدث خطأ: واجهة WebAccess غير متاحة"); return;
    }

    var entries;
    try { entries = webAccessApi.getFocusedEntries(); }
    catch (e) { alert("تعذر قراءة المستند المحدد"); return; }

    if (!entries || !entries.length)  { alert("رجاء اختيار مستند أولاً"); return; }
    if (entries.length > 1)           { alert("رجاء اختيار مستند واحد فقط"); return; }

    entryId = entries[0].id;
    if (window.__ocrRunningEntryId === entryId) return;
    window.__ocrRunningEntryId = entryId;
    if (btn) btn.classList.add("ocr-running");

    var fieldsById = {};
    var pageIds    = [];
    var pageTexts  = [];

    showOverlayLoading("جاري قراءة بيانات القالب...");

    postJson("/laserfiche/MetadataService.ashx/GetMetadata", {
        repoName: repoName, entryIds: [String(entryId)], metadataFlags: 1
    })
    .then(function (metaResult) {
        if (!metaResult || !metaResult.d || !metaResult.d.Fields)
            throw new Error("لا يمكن قراءة حقول القالب (تأكد إن للمستند قالب)");
        (metaResult.d.Fields.templateFields || []).forEach(function (f) {
            fieldsById[f.name] = f.id;
        });

        // نجمع pageIds قبل التصدير عشان نقدر نحدد العدد
        pageIds = fetchPageIds();

        showOverlayLoading("جاري تصدير المستند...");

        // لو عندنا العدد: تصدير متوازٍ. لو لأ: تسلسلي مع اكتشاف النهاية.
        if (pageIds.length > 0) {
            return exportAllParallel(pageIds.length);
        } else {
            return exportAllSequential();
        }
    })
    .then(function (pageBlobs) {
        if (!pageBlobs || !pageBlobs.length)
            throw new Error("لم يتم تصدير أي صفحة من المستند");
        console.log("ArabicOCR: اتصدّر " + pageBlobs.length + " صفحة");

        if (pageIds.length && pageIds.length !== pageBlobs.length) {
            console.warn(
                "ArabicOCR: عدد pageIds (" + pageIds.length +
                ") ≠ عدد الـ blobs (" + pageBlobs.length +
                "). افتح بانل Thumbnails ونزّل لآخره."
            );
        }

        return processPages(pageBlobs, Object.keys(fieldsById));
    })
    .then(function (processed) {
        var extracted = processed.fields || {};
        pageTexts = processed.texts || [];

        var fieldChanges = [];
        Object.keys(extracted).forEach(function (name) {
            if (fieldsById.hasOwnProperty(name) && extracted[name]) {
                fieldChanges.push({
                    fieldId:    fieldsById[name],
                    value:      String(extracted[name]).trim(),
                    remove:     false,
                    fieldIndex: 0
                });
            }
        });

        var hasText = pageTexts.some(function (t) { return t && t.length; });
        if (!fieldChanges.length && !hasText) {
            showOverlayResult("لم يتم التعرف على أي حقول أو نص في هذا المستند", true, textError);
            return null;
        }

        showOverlayLoading("جاري حفظ البيانات في المستند...");

        return refreshSession().then(function () {
            return postJson("/laserfiche/DocumentService.ashx/LockDocument", {
                repoName: repoName, documentId: entryId,
                lockEfile: false, autoCheckout: false
            });
        }).then(function () {
            documentWasLocked = true;
            // pageTexts هنا نصوص عادية، لكن saveAllPagesText بتتوقع { page, text }
            // فبنحوّلها للشكل المطلوب
            var pagesArr = pageTexts.map(function (t, i) {
                return { page: i + 1, text: t };
            });
            return saveAllPagesText(pageIds, pageTexts);
        }).then(function () {
            if (!fieldChanges.length)
                return unlockDocument().then(function () { return { d: true }; });
            return postJson("/laserfiche/DocumentService.ashx/SaveEntry", {
                repoName:  repoName,
                documentId: entryId,
                curPageNum: 0, strCurPageId: 0,
                changes: {
                    dirty: true, newTemplateId: 0, removeTemplate: false,
                    fieldChanges: fieldChanges, tagChanges: [], linkChanges: []
                },
                generalchanges: [], annchanges: []
            }).then(function (saveResult) {
                return unlockDocument().then(function () { return saveResult; });
            });
        });
    })
    .then(function (saveResult) {
        if (!saveResult) return;
        try { webAccessApi.refreshMetadata();    } catch (e) {}
        try { webAccessApi.refreshContentsPane(); } catch (e) {}
        showOverlayResult(
            "تم استخراج البيانات وحفظها بنجاح ✔",
            false,
            textError ? "⚠ ملاحظة على النص:\n" + textError : null
        );
        if (!textError) setTimeout(function () { location.reload(); }, 1500);
    })
    .catch(function (err) {
        console.error("ArabicOCR Error:", err);
        unlockDocument().then(function () {
            showOverlayResult(
                "حدث خطأ:\n" + (err && err.message || "خطأ غير متوقع"), true
            );
        });
    });
};
