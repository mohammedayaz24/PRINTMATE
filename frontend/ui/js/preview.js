/* global pdfjsLib */

const statusEl = document.getElementById("previewStatus");
const titleEl = document.getElementById("previewTitle");
const metaEl = document.getElementById("previewMeta");
const pagesEl = document.getElementById("pages");
const downloadBtn = document.getElementById("downloadBtn");
const closeBtn = document.getElementById("closeBtn");

let latestBytes = null;
let latestFilename = "printmate-preview.pdf";
let activeJobId = 0;

const PREVIEW_DB_NAME = "printmate";
const PREVIEW_DB_VERSION = 1;
const PREVIEW_STORE_NAME = "pdf_previews";

function getQueryParam(key) {
  try {
    return new URLSearchParams(window.location.search).get(key);
  } catch (_) {
    return null;
  }
}

function openPreviewDb() {
  if (!("indexedDB" in window)) {
    return Promise.reject(new Error("IndexedDB not available."));
  }

  return new Promise((resolve, reject) => {
    const request = indexedDB.open(PREVIEW_DB_NAME, PREVIEW_DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(PREVIEW_STORE_NAME)) {
        db.createObjectStore(PREVIEW_STORE_NAME, { keyPath: "id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("Failed to open IndexedDB."));
  });
}

function idbGet(db, key) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(PREVIEW_STORE_NAME, "readonly");
    const req = tx.objectStore(PREVIEW_STORE_NAME).get(key);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error || new Error("Failed to read from IndexedDB."));
  });
}

function idbDelete(db, key) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(PREVIEW_STORE_NAME, "readwrite");
    tx.objectStore(PREVIEW_STORE_NAME).delete(key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error || new Error("Failed to delete from IndexedDB."));
    tx.onabort = () => reject(tx.error || new Error("Failed to delete from IndexedDB."));
  });
}

function normalizeStoredBytes(record) {
  if (!record) return null;
  if (record.bytes instanceof Uint8Array) return record.bytes;
  if (record.bytes instanceof ArrayBuffer) return new Uint8Array(record.bytes);
  if (record.bytes && record.bytes.buffer instanceof ArrayBuffer) {
    return new Uint8Array(record.bytes.buffer);
  }
  return null;
}

async function waitForPreviewPayload(previewId, { timeoutMs = 15000, intervalMs = 250 } = {}) {
  const db = await openPreviewDb();
  const start = Date.now();

  try {
    while (Date.now() - start < timeoutMs) {
      const record = await idbGet(db, previewId);
      if (record) {
        try { await idbDelete(db, previewId); } catch (_) {}
        return record;
      }
      await new Promise(resolve => setTimeout(resolve, intervalMs));
    }
    return null;
  } finally {
    try { db.close(); } catch (_) {}
  }
}

function setStatus(message, tone = "") {
  if (!statusEl) return;
  statusEl.textContent = message || "";
  statusEl.classList.remove("error", "success", "loading");
  if (tone) statusEl.classList.add(tone);
}

function clearPages() {
  if (!pagesEl) return;
  pagesEl.textContent = "";
}

function safeOrigin() {
  // When served via file://, location.origin is "null". Use "*" in that case.
  return location.origin && location.origin !== "null" ? location.origin : "*";
}

function normalizeIncomingBytes(data) {
  if (!data) return null;
  if (data.bytes instanceof ArrayBuffer) return new Uint8Array(data.bytes);
  if (data.buffer instanceof ArrayBuffer) return new Uint8Array(data.buffer);
  if (data.bytes instanceof Uint8Array) return data.bytes;
  if (data.buffer instanceof Uint8Array) return data.buffer;
  return null;
}

function downloadBytes(bytes, filename) {
  const blob = new Blob([bytes], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename || "printmate-preview.pdf";
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

async function loadPdfDocument(bytes) {
  if (!window.pdfjsLib) {
    throw new Error("PDF.js not loaded.");
  }

  // Ensure the worker URL is correct (self-hosted).
  if (window.pdfjsLib.GlobalWorkerOptions) {
    window.pdfjsLib.GlobalWorkerOptions.workerSrc = "../vendor/pdfjs/pdf.worker.min.js";
  }

  let loadingTask = window.pdfjsLib.getDocument({ data: bytes });
  try {
    return await loadingTask.promise;
  } catch (err) {
    try { await loadingTask.destroy(); } catch (_) {}
    loadingTask = window.pdfjsLib.getDocument({ data: bytes, disableWorker: true });
    return await loadingTask.promise;
  }
}

async function renderAllPages(bytes, jobId) {
  if (!pagesEl) return;
  clearPages();

  const pdf = await loadPdfDocument(bytes);
  if (jobId !== activeJobId) return;

  const total = pdf.numPages || 0;
  metaEl && (metaEl.textContent = total ? `${total} page${total === 1 ? "" : "s"}` : "No pages");
  setStatus(total ? `Rendering… (0/${total})` : "No pages to render.", total ? "loading" : "error");

  for (let pageNumber = 1; pageNumber <= total; pageNumber += 1) {
    if (jobId !== activeJobId) return;
    setStatus(`Rendering… (${pageNumber}/${total})`, "loading");

    const wrapper = document.createElement("div");
    wrapper.className = "preview-page-item";

    const label = document.createElement("div");
    label.className = "preview-page-label";
    label.textContent = `Page ${pageNumber}`;

    const canvas = document.createElement("canvas");
    canvas.className = "preview-page-canvas";

    wrapper.appendChild(label);
    wrapper.appendChild(canvas);
    pagesEl.appendChild(wrapper);

    const page = await pdf.getPage(pageNumber);
    if (jobId !== activeJobId) return;

    const baseViewport = page.getViewport({ scale: 1 });
    const targetWidth = Math.max(1, wrapper.clientWidth || pagesEl.clientWidth || 900);
    const fitScale = targetWidth / baseViewport.width;
    const scale = Math.max(0.1, Math.min(fitScale, 3));
    const viewport = page.getViewport({ scale });

    const outputScale = window.devicePixelRatio || 1;
    const context = canvas.getContext("2d", { alpha: false });
    if (!context) throw new Error("Canvas not supported in this browser.");

    canvas.width = Math.floor(viewport.width * outputScale);
    canvas.height = Math.floor(viewport.height * outputScale);

    context.setTransform(outputScale, 0, 0, outputScale, 0, 0);
    context.imageSmoothingEnabled = true;
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, viewport.width, viewport.height);

    await page.render({ canvasContext: context, viewport }).promise;
    try { page.cleanup(); } catch (_) {}

    await new Promise(resolve => requestAnimationFrame(resolve));
  }

  if (jobId !== activeJobId) return;
  setStatus("Preview ready. Scroll to view all pages.", "success");
}

function applyIncomingPdf(bytes, filename) {
  latestBytes = bytes;
  latestFilename = filename || "printmate-preview.pdf";

  if (downloadBtn) downloadBtn.disabled = !latestBytes;
  if (titleEl) titleEl.textContent = latestFilename;

  const jobId = ++activeJobId;
  setStatus("Loading…", "loading");

  void renderAllPages(latestBytes, jobId).catch(err => {
    if (jobId !== activeJobId) return;
    clearPages();
    setStatus(err?.message || "Could not render preview.", "error");
  });
}

async function bootFromIndexedDb(previewId) {
  if (latestBytes) return;
  metaEl && (metaEl.textContent = "Waiting for document from the order page…");
  setStatus("Waiting…", "loading");

  let record = null;
  try {
    record = await waitForPreviewPayload(previewId);
  } catch (err) {
    if (latestBytes) return;
    setStatus(err?.message || "Could not load preview.", "error");
    return;
  }

  if (latestBytes) return;
  if (!record) {
    setStatus("Still waiting for the document… Go back and click “Open Preview” again.", "loading");
    return;
  }

  const bytes = normalizeStoredBytes(record);
  const filename = String(record.filename || "printmate-preview.pdf");
  if (!bytes) {
    setStatus("Invalid preview payload.", "error");
    return;
  }

  if (latestBytes) return;
  applyIncomingPdf(bytes, filename);
}

downloadBtn?.addEventListener("click", () => {
  if (!latestBytes) return;
  downloadBytes(latestBytes, latestFilename);
});

closeBtn?.addEventListener("click", () => {
  try { window.close(); } catch (_) {}
});

window.addEventListener("message", event => {
  const data = event?.data;
  if (!data || typeof data !== "object") return;

  if (data.type === "PRINTMATE_PREVIEW_INIT") {
    const channelId = data.channelId || null;
    try {
      const origin = event.origin && event.origin !== "null" ? event.origin : safeOrigin();
      event.source?.postMessage({ type: "PRINTMATE_PREVIEW_READY", channelId }, origin);
    } catch (_) {}
    return;
  }

  if (data.type === "PRINTMATE_PDF_PREVIEW") {
    const bytes = normalizeIncomingBytes(data);
    const filename = String(data.filename || "printmate-preview.pdf");
    if (!bytes) {
      setStatus("Invalid preview payload.", "error");
      return;
    }
    applyIncomingPdf(bytes, filename);
  }
});

const previewId = getQueryParam("preview_id") || getQueryParam("previewId");

if (previewId) {
  void bootFromIndexedDb(previewId);
} else {
  // If opened manually (without an opener), show a helpful hint.
  if (!window.opener) {
    setStatus('Open this page using the "Open Preview" button in the order screen.', "error");
    metaEl && (metaEl.textContent = "No opener detected.");
  }

  // If we have an opener but no payload arrives, show a hint after a short delay.
  setTimeout(() => {
    if (!window.opener) return;
    if (latestBytes) return;
    setStatus('Still waiting for the document... Go back and click "Open Preview" again.', "loading");
  }, 2500);
}
