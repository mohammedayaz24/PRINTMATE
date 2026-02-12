const fileInput = document.getElementById("fileInput");
const pageCountInput = document.getElementById("pageCount");
const fileNameInput = document.getElementById("fileName");
const uploadState = document.getElementById("uploadState");
const pageRanges = document.getElementById("pageRanges");
const colorMode = document.getElementById("colorMode");
const sideMode = document.getElementById("sideMode");
const orientation = document.getElementById("orientation");
const binding = document.getElementById("binding");
const copies = document.getElementById("copies");
const pricePreview = document.getElementById("pricePreview");
const previewBtn = document.getElementById("previewBtn");
const previewStrip = document.getElementById("previewStrip");
const previewPages = document.getElementById("previewPages");
const previewState = document.getElementById("previewState");
const createBtn = document.getElementById("createOrder");
const createState = document.getElementById("createState");
const shopTitle = document.getElementById("shopTitle");
const shopStatus = document.getElementById("shopStatus");
const shopMeta = document.getElementById("shopMeta");
const shopInfo = document.getElementById("shopInfo");
const shopBadge = document.getElementById("shopBadge");

// Safety limits (client-side).
const MAX_PDF_BYTES = 20 * 1024 * 1024; // 20MB
const BW_RENDER_SCALE = 2; // Higher = better quality, slower/larger.
const BW_JPEG_QUALITY = 0.92;
const LIVE_PREVIEW_MAX_PAGES = 8;

// Open Preview uses IndexedDB to avoid Blob URL partitioning issues in some browsers.
const PREVIEW_DB_NAME = "printmate";
const PREVIEW_DB_VERSION = 1;
const PREVIEW_STORE_NAME = "pdf_previews";

let selectedFile = null;
let originalBytes = null;
let transformedBytes = null;
let lastVectorKey = null;
let lastVectorBytes = null;
let lastVectorPageCount = 0;
let lastBwKey = null;
let lastBwBytes = null;
let activeTransformJob = 0;
let isProcessing = false;
let previewModal = null;
let previewModalBody = null;
let previewModalPages = null;
let previewModalStatusLabel = null;
let previewModalDownloadBtn = null;
let previewModalBytes = null;
let previewModalPdf = null;
let previewModalLoadingTask = null;
let previewModalRenderTask = null;
let previewModalTotalPages = 0;
let previewModalJob = 0;
let detectedPages = 0;
let shopId = null;
let shopOpen = false;

if (window.pdfjsLib && window.pdfjsLib.GlobalWorkerOptions) {
  window.pdfjsLib.GlobalWorkerOptions.workerSrc =
    "../vendor/pdfjs/pdf.worker.min.js";
}

function getQueryParam(key) {
  try {
    return new URLSearchParams(window.location.search).get(key);
  } catch (err) {
    return null;
  }
}

function formatCurrency(value) {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return "INR 0";
  try {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0
    }).format(numeric);
  } catch (err) {
    return "INR " + numeric;
  }
}

function calculateEstimate() {
  if (!detectedPages) {
    pricePreview.textContent = "INR 0";
    return 0;
  }

  const isColor = colorMode.value === "COLOR";
  const isDouble = sideMode.value === "DOUBLE";
  const isSpiral = binding.value === "SPIRAL";
  const copiesValue = Number(copies.value) || 1;

  const pageCost = isColor ? 5 : 1;
  const bindingCost = isSpiral ? 20 : 0;
  const effectivePages = isDouble ? Math.ceil(detectedPages / 2) : detectedPages;

  const total = (effectivePages * pageCost * copiesValue) + bindingCost;
  pricePreview.textContent = formatCurrency(total);
  return total;
}

function hashCode(input) {
  let hash = 0;
  const str = String(input);
  for (let i = 0; i < str.length; i += 1) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

function getShopMeta(id) {
  const hash = hashCode(id);
  const names = ["Campus Prints", "BlueLine Studio", "QuickCopy Hub", "Ink & Paper", "PrintPad"];
  const streets = ["North Avenue", "Library Road", "Main Street", "Science Park", "Hostel Lane"];
  const phones = ["+91 98765 43210", "+91 91234 56780", "+91 99887 76655", "+91 90909 12345", "+91 95555 22334"];
  return {
    name: names[hash % names.length],
    address: `${(hash % 90) + 10}, ${streets[hash % streets.length]}, City Campus`,
    contact: phones[hash % phones.length]
  };
}

function updateShopHeader(shop) {
  const meta = getShopMeta(shop.id);
  shopTitle.textContent = `Shop ${shop.id}`;
  shopMeta.textContent = `${meta.name} · ${meta.address}`;
  shopInfo.textContent = `Contact ${meta.contact} · Avg ${shop.avg_print_time_per_page ?? "-"} sec/page`;
  shopBadge.textContent = meta.name.split(" ").map(word => word[0]).slice(0, 2).join("");
  shopOpen = !!shop.accepting_orders;
  shopStatus.textContent = shopOpen ? "Accepting" : "Closed";
  shopStatus.className = `pill ${shopOpen ? "COMPLETED" : "CANCELLED"}`;
}

function setNote(el, message, tone = "") {
  if (!el) return;
  el.textContent = message || "";
  el.classList.remove("error", "success", "loading");
  if (tone) el.classList.add(tone);
}

function clearLivePreview() {
  if (!previewStrip) return;
  previewStrip.textContent = "";
}

function normalizeRanges(totalPages, rangesInput) {
  if (!rangesInput) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  const parts = rangesInput.split(",").map(part => part.trim()).filter(Boolean);
  const pages = new Set();

  parts.forEach(part => {
    if (part.includes("-")) {
      const [startRaw, endRaw] = part.split("-");
      const start = Number(startRaw);
      const end = Number(endRaw);
      if (!Number.isNaN(start) && !Number.isNaN(end)) {
        const from = Math.max(1, Math.min(start, end));
        const to = Math.min(totalPages, Math.max(start, end));
        for (let i = from; i <= to; i += 1) {
          pages.add(i);
        }
      }
    } else {
      const page = Number(part);
      if (!Number.isNaN(page) && page >= 1 && page <= totalPages) {
        pages.add(page);
      }
    }
  });

  const list = Array.from(pages).sort((a, b) => a - b);
  return list.length ? list : Array.from({ length: totalPages }, (_, i) => i + 1);
}

function isProbablyPdf(file) {
  if (!file) return false;
  if (file.type === "application/pdf") return true;
  const name = String(file.name || "").toLowerCase();
  return name.endsWith(".pdf");
}

async function transformPdf(bytes) {
  const pdfDoc = await PDFLib.PDFDocument.load(bytes);
  const totalPages = pdfDoc.getPageCount();
  const pagesToKeep = normalizeRanges(totalPages, pageRanges.value);
  const outputDoc = await PDFLib.PDFDocument.create();

  for (const pageNumber of pagesToKeep) {
    const [copiedPage] = await outputDoc.copyPages(pdfDoc, [pageNumber - 1]);
    if (orientation.value === "LANDSCAPE") {
      copiedPage.setRotation(PDFLib.degrees(90));
    } else {
      copiedPage.setRotation(PDFLib.degrees(0));
    }
    outputDoc.addPage(copiedPage);
  }

  return {
    bytes: await outputDoc.save(),
    pageCount: pagesToKeep.length
  };
}

function getTransformKey() {
  return JSON.stringify({
    ranges: String(pageRanges.value || "").trim(),
    orientation: orientation.value
  });
}

async function canvasToBlob(canvas, type, quality) {
  return await new Promise((resolve, reject) => {
    canvas.toBlob(blob => {
      if (!blob) {
        reject(new Error("Canvas export failed."));
        return;
      }
      resolve(blob);
    }, type, quality);
  });
}

/**
 * Converts a PDF File/Blob into a grayscale PDF Blob.
 * Uses PDF.js to rasterize each page -> converts pixels to grayscale -> PDF-Lib rebuilds a PDF from images.
 *
 * @param {File|Blob} pdfFile
 * @param {object} options
 * @param {number} options.scale Render scale (quality vs speed/size)
 * @param {number} options.jpegQuality JPEG quality for embedded page images
 * @param {(current:number,total:number)=>void} options.onProgress Progress callback
 * @returns {Promise<Blob>} application/pdf Blob
 */
async function convertPdfToGrayscaleBlob(
  pdfFile,
  { scale = BW_RENDER_SCALE, jpegQuality = BW_JPEG_QUALITY, onProgress } = {}
) {
  if (!window.pdfjsLib && !window.PDFLib) {
    throw new Error("PDF.js and PDF-Lib failed to load. Run PRINTMATE/scripts/vendor-download.ps1 and reload.");
  }
  if (!window.pdfjsLib) {
    throw new Error("PDF.js failed to load, so Black & White conversion is unavailable. Run PRINTMATE/scripts/vendor-download.ps1 and reload.");
  }
  if (!window.PDFLib) {
    throw new Error("PDF-Lib failed to load, so PDF processing is unavailable. Run PRINTMATE/scripts/vendor-download.ps1 and reload.");
  }

  const pdfBytes = new Uint8Array(await pdfFile.arrayBuffer());
  let loadingTask = window.pdfjsLib.getDocument({ data: pdfBytes });
  let pdf;

  try {
    try {
      pdf = await loadingTask.promise;
    } catch (err) {
      // Some environments block web workers (or the worker script). Retry without a worker.
      try { await loadingTask.destroy(); } catch (_) {}
      loadingTask = window.pdfjsLib.getDocument({ data: pdfBytes, disableWorker: true });
      pdf = await loadingTask.promise;
    }
    const outputDoc = await PDFLib.PDFDocument.create();

    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) {
      throw new Error("Canvas is not supported in this browser.");
    }

    const PDF_TO_CSS_UNITS = 96 / 72;

    for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
      if (typeof onProgress === "function") onProgress(pageNumber, pdf.numPages);

      const page = await pdf.getPage(pageNumber);
      const baseViewport = page.getViewport({ scale: 1 });
      const viewport = page.getViewport({ scale });

      canvas.width = Math.ceil(viewport.width);
      canvas.height = Math.ceil(viewport.height);

      context.save();
      context.setTransform(1, 0, 0, 1, 0, 0);
      context.fillStyle = "#ffffff";
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.restore();

      await page.render({ canvasContext: context, viewport }).promise;
      page.cleanup();

      const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
      const data = imageData.data;

      // Grayscale conversion (luma): Y = 0.2126R + 0.7152G + 0.0722B
      for (let i = 0; i < data.length; i += 4) {
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];
        const y = Math.round(0.2126 * r + 0.7152 * g + 0.0722 * b);
        data[i] = y;
        data[i + 1] = y;
        data[i + 2] = y;
      }

      context.putImageData(imageData, 0, 0);

      const pageBlob = await canvasToBlob(canvas, "image/jpeg", jpegQuality);
      const pageBytes = new Uint8Array(await pageBlob.arrayBuffer());
      const pageImage = await outputDoc.embedJpg(pageBytes);

      // Preserve original page size (in PDF points) to avoid oversized/cropped output.
      const pageWidthPts = baseViewport.width / PDF_TO_CSS_UNITS;
      const pageHeightPts = baseViewport.height / PDF_TO_CSS_UNITS;

      const outPage = outputDoc.addPage([pageWidthPts, pageHeightPts]);
      outPage.drawImage(pageImage, {
        x: 0,
        y: 0,
        width: pageWidthPts,
        height: pageHeightPts
      });
    }

    const outBytes = await outputDoc.save();
    const outBlob = new Blob([outBytes], { type: "application/pdf" });
    if (outBlob.size > MAX_PDF_BYTES) {
      throw new Error("Converted PDF is larger than 20MB. Reduce pages or use Color mode.");
    }
    return outBlob;
  } finally {
    try {
      if (pdf) pdf.cleanup();
      await loadingTask.destroy();
    } catch (err) {
      // ignore cleanup errors
    }
  }
}

async function buildVectorPdfIfNeeded() {
  if (!originalBytes) {
    throw new Error("No PDF loaded.");
  }

  const key = getTransformKey();
  if (lastVectorBytes && lastVectorKey === key) {
    return { key, bytes: lastVectorBytes, pageCount: lastVectorPageCount };
  }

  const result = await transformPdf(originalBytes);
  lastVectorKey = key;
  lastVectorBytes = result.bytes;
  lastVectorPageCount = result.pageCount;
  lastBwKey = null;
  lastBwBytes = null;
  return { key, bytes: result.bytes, pageCount: result.pageCount };
}

async function buildOutputBytes(vectorResult) {
  if (colorMode.value !== "BW") return vectorResult.bytes;

  if (lastBwBytes && lastBwKey === vectorResult.key) return lastBwBytes;

  const inputBlob = new Blob([vectorResult.bytes], { type: "application/pdf" });
  const bwBlob = await convertPdfToGrayscaleBlob(inputBlob, {
    onProgress: (current, total) => {
      setNote(previewState, `Converting to black & white… (${current}/${total})`, "loading");
    }
  });
  const bwBytes = new Uint8Array(await bwBlob.arrayBuffer());
  lastBwKey = vectorResult.key;
  lastBwBytes = bwBytes;
  return bwBytes;
}

async function updateTransformedPreview({ render = true } = {}) {
  if (!originalBytes) return false;

  const jobId = ++activeTransformJob;
  isProcessing = true;
  createBtn.disabled = true;
  previewBtn.disabled = true;
  setNote(previewState, "Updating preview…", "loading");

  try {
    const vectorResult = await buildVectorPdfIfNeeded();
    if (jobId !== activeTransformJob) return false;

    detectedPages = vectorResult.pageCount;
    pageCountInput.value = detectedPages;
    previewPages.textContent = detectedPages ? `${detectedPages} pages` : "0 pages";
    calculateEstimate();

    // Build the final bytes to upload (vector for Color, raster-grayscale for BW).
    try {
      transformedBytes = await buildOutputBytes(vectorResult);
      if (jobId !== activeTransformJob) return false;
    } catch (err) {
      // Keep detected pages/estimate, but block order creation until conversion succeeds.
      transformedBytes = null;
      setNote(previewState, err?.message || "Could not prepare the PDF.", "error");
      return false;
    }

    // Preview rendering is optional. If PDF.js is blocked, use "Open Preview" to view the PDF.
    if (render) {
      try {
        const previewSummary = await renderPreview(transformedBytes, jobId);
        if (jobId !== activeTransformJob) return false;
        const rendered = Number(previewSummary?.rendered || 0);
        const total = Number(previewSummary?.total || 0);
        if (total && rendered && rendered < total) {
          setNote(previewState, `Showing ${rendered}/${total} pages. Use “Open Preview” for all pages.`, "success");
        } else {
          setNote(previewState, "Preview ready.", "success");
        }
      } catch (err) {
        clearLivePreview();
        setNote(previewState, "Preview unavailable. You can still open “Open Preview”.", "error");
      }
    } else {
      setNote(previewState, "");
    }

    return true;
  } catch (err) {
    transformedBytes = null;
    detectedPages = 0;
    pageCountInput.value = "";
    previewPages.textContent = "0 pages";
    clearLivePreview();
    calculateEstimate();
    setNote(previewState, err?.message || "Preview unavailable.", "error");
    return false;
  } finally {
    if (jobId === activeTransformJob) {
      isProcessing = false;
      createBtn.disabled = false;
      previewBtn.disabled = false;
    }
  }
}

async function renderPreview(bytes, jobId) {
  if (!bytes || !previewStrip) return { rendered: 0, total: 0 };
  if (!window.pdfjsLib) {
    throw new Error("Preview unavailable (PDF.js not loaded).");
  }

  clearLivePreview();

  const strip = previewStrip;
  const container = strip.parentElement;
  const availableHeight = Math.max(1, (container?.clientHeight || 220) - 24);
  const targetHeight = Math.max(1, Math.min(availableHeight, 190));

  // Load the PDF (retry without worker if the worker can't start).
  let loadingTask = window.pdfjsLib.getDocument({ data: bytes });
  let pdf;

  try {
    try {
      pdf = await loadingTask.promise;
    } catch (err) {
      try { await loadingTask.destroy(); } catch (_) {}
      loadingTask = window.pdfjsLib.getDocument({ data: bytes, disableWorker: true });
      pdf = await loadingTask.promise;
    }

    if (jobId !== activeTransformJob) return { rendered: 0, total: 0, aborted: true };

    const total = Number(pdf?.numPages || 0);
    const rendered = Math.min(total, LIVE_PREVIEW_MAX_PAGES);

    for (let pageNumber = 1; pageNumber <= rendered; pageNumber += 1) {
      if (jobId !== activeTransformJob) return { rendered: 0, total, aborted: true };

      const canvas = document.createElement("canvas");
      canvas.className = "preview-thumb";
      canvas.setAttribute("aria-label", `Preview page ${pageNumber}`);
      strip.appendChild(canvas);

      const page = await pdf.getPage(pageNumber);
      if (jobId !== activeTransformJob) return { rendered: 0, total, aborted: true };

      const baseViewport = page.getViewport({ scale: 1 });
      const fitScale = targetHeight / Math.max(1, baseViewport.height);
      const scale = Math.max(0.08, Math.min(fitScale, 2));
      const viewport = page.getViewport({ scale });

      const outputScale = window.devicePixelRatio || 1;
      const context = canvas.getContext("2d", { alpha: false });
      if (!context) throw new Error("Canvas is not supported in this browser.");

      canvas.style.width = `${Math.floor(viewport.width)}px`;
      canvas.style.height = `${Math.floor(viewport.height)}px`;
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

    return { rendered, total };
  } finally {
    try { await loadingTask.destroy(); } catch (_) {}
  }
}

function updateFileInfo(file) {
  fileNameInput.value = file ? file.name : "";
}

function downloadPdfBytes(bytes, filename = "printmate-preview.pdf") {
  if (!bytes) return;
  const blob = new Blob([bytes], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

function copyBytesToArrayBuffer(bytes) {
  if (!bytes) return null;
  if (bytes instanceof ArrayBuffer) return bytes.slice(0);
  if (bytes instanceof Uint8Array) {
    return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  }
  if (bytes.buffer instanceof ArrayBuffer) {
    return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  }
  return null;
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

async function persistPreviewPayload(payload) {
  const db = await openPreviewDb();
  try {
    await new Promise((resolve, reject) => {
      const tx = db.transaction(PREVIEW_STORE_NAME, "readwrite");
      tx.objectStore(PREVIEW_STORE_NAME).put(payload);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error || new Error("Failed to store preview payload."));
      tx.onabort = () => reject(tx.error || new Error("Failed to store preview payload."));
    });
  } finally {
    try { db.close(); } catch (_) {}
  }
}

function openPreviewInNewTab(bytes) {
  const buffer = copyBytesToArrayBuffer(bytes);
  if (!buffer) return false;

  const previewId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const filename = String(selectedFile?.name || "printmate-preview.pdf");

  let previewWindow = null;
  try {
    const previewUrl = new URL(`preview.html?preview_id=${encodeURIComponent(previewId)}`, window.location.href).toString();
    previewWindow = window.open(previewUrl, "_blank");
  } catch (_) {
    previewWindow = null;
  }

  if (!previewWindow) return false;

  const payload = {
    id: previewId,
    filename,
    createdAt: Date.now(),
    bytes: buffer
  };

  void persistPreviewPayload(payload).catch(() => {
    // Fallback if IndexedDB fails: send bytes directly (may be slower for large PDFs).
    try {
      previewWindow.postMessage({ type: "PRINTMATE_PDF_PREVIEW", bytes: buffer, filename }, "*");
    } catch (_) {}
  });

  return true;
}

function clearPreviewModalPages() {
  if (!previewModalPages) return;
  previewModalPages.textContent = "";
}

function setPreviewModalStatus(message) {
  if (!previewModalStatusLabel) return;
  previewModalStatusLabel.textContent = message || "";
}

function closePreviewModal() {
  if (!previewModal) return;
  previewModalJob += 1;
  previewModal.classList.remove("open");

  try { previewModalRenderTask?.cancel(); } catch (_) {}
  previewModalRenderTask = null;

  try { previewModalPdf?.cleanup(); } catch (_) {}
  previewModalPdf = null;

  try { previewModalLoadingTask?.destroy(); } catch (_) {}
  previewModalLoadingTask = null;

  previewModalTotalPages = 0;
  previewModalBytes = null;
  setPreviewModalStatus("");
  clearPreviewModalPages();
  if (previewModalDownloadBtn) previewModalDownloadBtn.disabled = true;
}

function ensurePreviewModal() {
  if (previewModal) return;

  previewModal = document.createElement("div");
  previewModal.className = "preview-modal";
  previewModal.innerHTML = `
    <div class="preview-modal-card" role="dialog" aria-modal="true" aria-label="PDF preview">
      <div class="preview-modal-header">
        <div class="preview-modal-title">Preview</div>
        <div class="actions">
          <div class="preview-modal-page" data-preview-status></div>
          <button class="btn ghost" type="button" data-preview-download>Download</button>
          <button class="btn ghost" type="button" data-preview-close>Close</button>
        </div>
      </div>
      <div class="preview-modal-body">
        <div class="preview-modal-pages" data-preview-pages></div>
      </div>
    </div>
  `;

  document.body.appendChild(previewModal);
  previewModalBody = previewModal.querySelector(".preview-modal-body");
  previewModalPages = previewModal.querySelector("[data-preview-pages]");
  previewModalStatusLabel = previewModal.querySelector("[data-preview-status]");
  previewModalDownloadBtn = previewModal.querySelector("[data-preview-download]");

  if (previewModalDownloadBtn) previewModalDownloadBtn.disabled = true;

  const closeBtn = previewModal.querySelector("[data-preview-close]");
  closeBtn?.addEventListener("click", closePreviewModal);

  previewModalDownloadBtn?.addEventListener("click", () => {
    if (!previewModalBytes) return;
    const originalName = String(selectedFile?.name || "printmate-preview.pdf");
    const safeName = originalName.toLowerCase().endsWith(".pdf") ? originalName : `${originalName}.pdf`;
    downloadPdfBytes(previewModalBytes, safeName);
  });

  previewModal.addEventListener("click", event => {
    if (event.target === previewModal) closePreviewModal();
  });

  document.addEventListener("keydown", event => {
    if (!previewModal?.classList.contains("open")) return;
    if (event.key === "Escape") closePreviewModal();
  });
}

async function renderPreviewModalAllPages(jobId) {
  if (!previewModal?.classList.contains("open")) return;
  if (!previewModalPdf || !previewModalPages) return;
  if (jobId !== previewModalJob) return;

  clearPreviewModalPages();

  const total = previewModalTotalPages || previewModalPdf.numPages || 0;
  if (!total) {
    setPreviewModalStatus("No pages to preview.");
    return;
  }

  setPreviewModalStatus(`Rendering… (0/${total})`);

  for (let pageNumber = 1; pageNumber <= total; pageNumber += 1) {
    if (jobId !== previewModalJob) return;
    setPreviewModalStatus(`Rendering… (${pageNumber}/${total})`);

    const wrapper = document.createElement("div");
    wrapper.className = "preview-modal-page-item";

    const label = document.createElement("div");
    label.className = "preview-modal-page-label";
    label.textContent = `Page ${pageNumber}`;

    const canvas = document.createElement("canvas");
    canvas.className = "preview-modal-page-canvas";

    wrapper.appendChild(label);
    wrapper.appendChild(canvas);
    previewModalPages.appendChild(wrapper);

    const page = await previewModalPdf.getPage(pageNumber);
    if (jobId !== previewModalJob) return;

    const baseViewport = page.getViewport({ scale: 1 });
    const targetWidth = Math.max(1, wrapper.clientWidth || previewModalPages.clientWidth || 900);
    const fitScale = targetWidth / baseViewport.width;
    const scale = Math.max(0.1, Math.min(fitScale, 3));
    const viewport = page.getViewport({ scale });

    const outputScale = window.devicePixelRatio || 1;
    const context = canvas.getContext("2d", { alpha: false });
    if (!context) throw new Error("Canvas is not supported in this browser.");

    canvas.width = Math.floor(viewport.width * outputScale);
    canvas.height = Math.floor(viewport.height * outputScale);

    context.setTransform(outputScale, 0, 0, outputScale, 0, 0);
    context.imageSmoothingEnabled = true;
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, viewport.width, viewport.height);

    try { previewModalRenderTask?.cancel(); } catch (_) {}
    previewModalRenderTask = page.render({ canvasContext: context, viewport });
    try {
      await previewModalRenderTask.promise;
    } catch (err) {
      if (jobId === previewModalJob) throw err;
    } finally {
      previewModalRenderTask = null;
      try { page.cleanup(); } catch (_) {}
    }

    await new Promise(resolve => requestAnimationFrame(resolve));
  }

  if (jobId !== previewModalJob) return;
  setPreviewModalStatus(`${total} page${total === 1 ? "" : "s"} • Scroll to view`);
}

async function openPreviewModal(bytes) {
  if (!bytes) return;
  ensurePreviewModal();
  if (!previewModal || !previewModalBody || !previewModalPages) return;

  // Reset any previous modal state without tearing down the DOM.
  previewModalJob += 1;
  const jobId = previewModalJob;

  try { previewModalRenderTask?.cancel(); } catch (_) {}
  previewModalRenderTask = null;

  try { previewModalPdf?.cleanup(); } catch (_) {}
  previewModalPdf = null;

  try { await previewModalLoadingTask?.destroy(); } catch (_) {}
  previewModalLoadingTask = null;

  previewModalBytes = bytes;
  previewModalTotalPages = 0;
  clearPreviewModalPages();
  setPreviewModalStatus("Loading…");
  if (previewModalDownloadBtn) previewModalDownloadBtn.disabled = false;

  previewModal.classList.add("open");
  previewModalBody.scrollTop = 0;

  if (!window.pdfjsLib) {
    setPreviewModalStatus("Preview unavailable (PDF.js not loaded).");
    return;
  }

  // Load the PDF (retry without worker if needed).
  let loadingTask = window.pdfjsLib.getDocument({ data: bytes });
  previewModalLoadingTask = loadingTask;
  try {
    try {
      previewModalPdf = await loadingTask.promise;
    } catch (err) {
      try { await loadingTask.destroy(); } catch (_) {}
      loadingTask = window.pdfjsLib.getDocument({ data: bytes, disableWorker: true });
      previewModalLoadingTask = loadingTask;
      previewModalPdf = await loadingTask.promise;
    }
  } catch (err) {
    if (jobId !== previewModalJob) return;
    setPreviewModalStatus("Could not load PDF preview.");
    return;
  }

  if (jobId !== previewModalJob) return;
  previewModalTotalPages = previewModalPdf?.numPages || 0;
  await renderPreviewModalAllPages(jobId);
}

function loadShop() {
  shopId = getQueryParam("shop_id");
  if (!shopId) {
    setNote(createState, "Missing shop id in URL.", "error");
    return;
  }

  api.get("/shops")
    .then(res => {
      const shops = Array.isArray(res.data) ? res.data : [];
      const shop = shops.find(item => String(item.id) === String(shopId));
      if (!shop) {
        setNote(createState, "Shop not found.", "error");
        return;
      }
      updateShopHeader(shop);
    })
    .catch(() => {
      setNote(createState, "Failed to load shop details.", "error");
    });
}

fileInput.addEventListener("change", async event => {
  selectedFile = event.target.files[0];
  if (!selectedFile) return;

  transformedBytes = null;
  originalBytes = null;
  lastVectorKey = null;
  lastVectorBytes = null;
  lastVectorPageCount = 0;
  lastBwKey = null;
  lastBwBytes = null;
  detectedPages = 0;
  clearLivePreview();

  setNote(uploadState, "");
  setNote(createState, "");
  setNote(previewState, "Preparing preview…", "loading");
  updateFileInfo(selectedFile);

  if (!isProbablyPdf(selectedFile)) {
    setNote(uploadState, "Please upload a PDF file.", "error");
    fileInput.value = "";
    updateFileInfo(null);
    clearLivePreview();
    setNote(previewState, "Upload a PDF to preview changes.");
    return;
  }

  if (selectedFile.size > MAX_PDF_BYTES) {
    setNote(uploadState, "PDF too large. Max size is 20MB.", "error");
    fileInput.value = "";
    updateFileInfo(null);
    clearLivePreview();
    setNote(previewState, "Upload a PDF to preview changes.");
    return;
  }

  try {
    originalBytes = new Uint8Array(await selectedFile.arrayBuffer());
  } catch (err) {
    setNote(uploadState, "Could not read the file. Please try again.", "error");
    clearLivePreview();
    return;
  }

  const ok = await updateTransformedPreview({ render: true });
  setNote(uploadState, ok ? "PDF loaded." : "Could not process PDF.", ok ? "success" : "error");
});

let rangeDebounceTimer = null;
function debouncedUpdatePreview() {
  if (!originalBytes) return;
  if (rangeDebounceTimer) clearTimeout(rangeDebounceTimer);
  rangeDebounceTimer = setTimeout(() => updateTransformedPreview({ render: true }), 450);
}

pageRanges.addEventListener("input", () => debouncedUpdatePreview());
pageRanges.addEventListener("change", () => updateTransformedPreview({ render: true }));
orientation.addEventListener("change", () => updateTransformedPreview({ render: true }));
colorMode.addEventListener("change", () => {
  calculateEstimate();
  updateTransformedPreview({ render: true });
});

[sideMode, binding, copies].forEach(el => {
  el.addEventListener("change", () => calculateEstimate());
  el.addEventListener("input", () => calculateEstimate());
});

previewBtn.addEventListener("click", event => {
  event.preventDefault();
  if (!transformedBytes) {
    setNote(previewState, "Nothing to preview yet. Upload a PDF first.", "error");
    return;
  }
  const opened = openPreviewInNewTab(transformedBytes);
  if (opened) {
    setNote(previewState, "Opened preview in a new tab.", "success");
    return;
  }

  // Fallback (popup blocked): render an in-page preview.
  void openPreviewModal(transformedBytes).catch(err => {
    setNote(previewState, err?.message || "Could not open preview.", "error");
  });
});

createBtn.addEventListener("click", async () => {
  if (isProcessing) {
    setNote(createState, "Please wait — processing your PDF.", "loading");
    return;
  }
  if (!selectedFile || !transformedBytes) {
    setNote(createState, "PDF not ready. Fix the preview errors or switch to Color mode.", "error");
    return;
  }
  if (!detectedPages) {
    setNote(createState, "Page count not detected.", "error");
    return;
  }
  if (!shopId) {
    setNote(createState, "Missing shop id.", "error");
    return;
  }
  if (!shopOpen) {
    setNote(createState, "Selected shop is not accepting orders.", "error");
    return;
  }

  const estimatedCost = calculateEstimate();
  setNote(createState, "Preparing document…", "loading");

  try {
    const ok = await updateTransformedPreview({ render: false });
    if (!ok || !transformedBytes) {
      setNote(createState, "Could not prepare the PDF for upload.", "error");
      return;
    }

    setNote(createState, "Creating order…", "loading");
    const orderRes = await api.post("/orders", {
      student_id: window.STUDENT_ID,
      shop_id: shopId,
      total_pages: detectedPages,
      estimated_cost: estimatedCost
    });

    const orderId = orderRes.data.id;

    const formData = new FormData();
    const uploadBlob = new Blob([transformedBytes], { type: "application/pdf" });
    formData.append("file", uploadBlob, selectedFile.name || "document.pdf");
    await api.post(`/student/orders/${orderId}/upload`, formData, {
      headers: { "Content-Type": "multipart/form-data" }
    });

    await api.post(`/student/orders/${orderId}/print-options`, {
      page_ranges: pageRanges.value.trim(),
      color_mode: colorMode.value,
      side_mode: sideMode.value,
      orientation: orientation.value,
      binding: binding.value,
      copies: Number(copies.value) || 1
    });

    setNote(createState, "Order created successfully. Redirecting…", "success");
    setTimeout(() => {
      window.location.href = "index.html";
    }, 900);
  } catch (err) {
    setNote(createState, "Failed to create order. Please try again.", "error");
  }
});

loadShop();
calculateEstimate();
