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
const previewCanvas = document.getElementById("previewCanvas");
const previewPages = document.getElementById("previewPages");
const previewState = document.getElementById("previewState");
const createBtn = document.getElementById("createOrder");
const createState = document.getElementById("createState");
const shopTitle = document.getElementById("shopTitle");
const shopStatus = document.getElementById("shopStatus");
const shopMeta = document.getElementById("shopMeta");
const shopInfo = document.getElementById("shopInfo");
const shopBadge = document.getElementById("shopBadge");

let selectedFile = null;
let originalBytes = null;
let transformedBytes = null;
let previewUrl = null;
let detectedPages = 0;
let shopId = null;
let shopOpen = false;

if (window.pdfjsLib && window.pdfjsLib.GlobalWorkerOptions) {
  window.pdfjsLib.GlobalWorkerOptions.workerSrc =
    "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.2.67/pdf.worker.min.js";
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

async function detectPagesFromBytes(bytes) {
  try {
    const pdf = await window.pdfjsLib.getDocument({ data: bytes }).promise;
    return pdf.numPages || 0;
  } catch (err) {
    return 0;
  }
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

async function buildPdfFromImage(file) {
  const arrayBuffer = await file.arrayBuffer();
  const pdfDoc = await PDFLib.PDFDocument.create();
  let image;

  if (file.type === "image/png") {
    image = await pdfDoc.embedPng(arrayBuffer);
  } else {
    image = await pdfDoc.embedJpg(arrayBuffer);
  }

  const page = pdfDoc.addPage([image.width, image.height]);
  page.drawImage(image, { x: 0, y: 0, width: image.width, height: image.height });
  return await pdfDoc.save();
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

async function updateTransformedPreview() {
  if (!originalBytes) return;
  previewState.textContent = "Updating preview...";

  try {
    if (selectedFile && selectedFile.type.startsWith("image/")) {
      transformedBytes = await buildPdfFromImage(selectedFile);
      detectedPages = 1;
    } else {
      const result = await transformPdf(originalBytes);
      transformedBytes = result.bytes;
      detectedPages = result.pageCount;
    }
    pageCountInput.value = detectedPages;
    previewPages.textContent = detectedPages ? `${detectedPages} pages` : "0 pages";
    calculateEstimate();
    await renderPreview(transformedBytes);
  } catch (err) {
    previewState.textContent = "Preview unavailable.";
  }
}

async function renderPreview(bytes) {
  if (!bytes || !previewCanvas) return;
  const pdf = await window.pdfjsLib.getDocument({ data: bytes }).promise;
  const page = await pdf.getPage(1);
  const viewport = page.getViewport({ scale: 1.2 });
  const context = previewCanvas.getContext("2d");
  previewCanvas.width = viewport.width;
  previewCanvas.height = viewport.height;
  await page.render({ canvasContext: context, viewport }).promise;
  previewState.textContent = "Preview ready.";
}

function updateFileInfo(file) {
  fileNameInput.value = file ? file.name : "";
}

function releasePreviewUrl() {
  if (previewUrl) {
    URL.revokeObjectURL(previewUrl);
    previewUrl = null;
  }
}

function loadShop() {
  shopId = getQueryParam("shop_id");
  if (!shopId) {
    createState.textContent = "Missing shop id in URL.";
    return;
  }

  api.get("/shops")
    .then(res => {
      const shops = Array.isArray(res.data) ? res.data : [];
      const shop = shops.find(item => String(item.id) === String(shopId));
      if (!shop) {
        createState.textContent = "Shop not found.";
        return;
      }
      updateShopHeader(shop);
    })
    .catch(() => {
      createState.textContent = "Failed to load shop details.";
    });
}

fileInput.addEventListener("change", async event => {
  selectedFile = event.target.files[0];
  if (!selectedFile) return;

  uploadState.textContent = "Analyzing document...";
  updateFileInfo(selectedFile);

  if (selectedFile.type.startsWith("image/")) {
    originalBytes = await buildPdfFromImage(selectedFile);
  } else {
    originalBytes = new Uint8Array(await selectedFile.arrayBuffer());
  }

  await updateTransformedPreview();
  uploadState.textContent = detectedPages ? "Pages detected." : "Could not detect pages.";
});

[pageRanges, colorMode, sideMode, orientation, binding, copies].forEach(el => {
  el.addEventListener("change", () => {
    calculateEstimate();
    updateTransformedPreview();
  });
  el.addEventListener("input", () => {
    calculateEstimate();
  });
});

previewBtn.addEventListener("click", () => {
  if (!transformedBytes) return;
  releasePreviewUrl();
  const blob = new Blob([transformedBytes], { type: "application/pdf" });
  previewUrl = URL.createObjectURL(blob);
  window.open(previewUrl, "_blank");
});

createBtn.addEventListener("click", async () => {
  if (!selectedFile || !transformedBytes) {
    createState.textContent = "Please upload a document first.";
    return;
  }
  if (!detectedPages) {
    createState.textContent = "Page count not detected.";
    return;
  }
  if (!shopId) {
    createState.textContent = "Missing shop id.";
    return;
  }
  if (!shopOpen) {
    createState.textContent = "Selected shop is not accepting orders.";
    return;
  }

  const estimatedCost = calculateEstimate();
  createState.textContent = "Creating order...";

  try {
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

    createState.textContent = "Order created successfully. Redirecting...";
    setTimeout(() => {
      window.location.href = "index.html";
    }, 900);
  } catch (err) {
    createState.textContent = "Failed to create order. Please try again.";
  }
});

loadShop();
calculateEstimate();
