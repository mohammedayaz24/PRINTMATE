// Load and render a single shop's details by ID
function loadShopDetails(shopId) {
  if (!shopId) return;
  shopState.textContent = "Loading shop details...";
  api.get(`/shops/${shopId}`)
    .then(res => {
      const shop = res.data;
      // Render shop details in a target element (customize as needed)
      const detailsDiv = document.getElementById("shopDetails");
      if (!detailsDiv) return;
      detailsDiv.innerHTML = `
        <h2>${shop.shop_name ?? "Shop"}</h2>
        <div><strong>Address:</strong> ${shop.address ?? "-"}</div>
        <div><strong>Phone:</strong> ${shop.phone ?? "-"}</div>
        <div><strong>Status:</strong> ${shop.accepting_orders ? "Accepting Orders" : "Busy"}</div>
        <div><strong>Avg Print Time:</strong> ${shop.avg_print_time_per_page ?? "-"} s/page</div>
      `;
      shopState.textContent = "";
    })
    .catch(() => {
      shopState.textContent = "Failed to load shop details.";
    });
}
// PRINTMATE - Shops (student)
// Renders Amazon-style expandable cards with details inside each card.
// Backend endpoint stays the same: GET /shops

const shopGrid = document.getElementById("shopGrid");
const shopState = document.getElementById("shopState");

let expandedCard = null;

const PRICING = [
  { label: "Black & white", value: "INR 1 / page" },
  { label: "Color", value: "INR 5 / page" },
  { label: "Spiral binding", value: "INR 20" },
];

// Placeholder data (frontend-only).
const PLACEHOLDER_NAMES = [
  "PrintMate Central",
  "Campus Copy Hub",
  "QuickPrint Studio",
  "Library Print Desk",
  "Metro Print & Bind",
  "Express Document Center",
];

const PLACEHOLDER_DESCRIPTIONS = [
  "Fast & reliable printing near campus.",
  "Best for bulk prints and tight deadlines.",
  "Sharp color prints and clean finishing.",
  "Affordable black & white prints for notes.",
  "Binding specialists with quick turnaround.",
  "Perfect for last-minute submissions.",
];

const PLACEHOLDER_CONTACTS = [
  "+91 98765 43210",
  "+91 91234 56789",
  "+91 99887 77665",
  "+91 90000 12345",
  "+91 95555 11122",
  "+91 96666 33344",
];

const PLACEHOLDER_ADDRESSES = [
  "Near Campus Road, City Center",
  "Main Gate, College Campus",
  "Opp. Station Road, Downtown",
  "Library Building, Ground Floor",
  "Market Street, 2nd Floor",
  "Tech Park, Block B",
];

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false;
}

function toSafeNumber(value) {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : null;
}

function pickByShopId(list, shopId) {
  const raw = toSafeNumber(shopId) ?? 0;
  const index = Math.abs(raw) % list.length;
  return list[index];
}

function computeHue(shopId) {
  // Deterministic but varied per shop, used by CSS via --shop-hue.
  const raw = Math.abs(toSafeNumber(shopId) ?? 0);
  return (raw * 47) % 360;
}

function formatAvgTime(avg) {
  const numberValue = toSafeNumber(avg);
  return numberValue == null ? "-" : `${numberValue}s / page`;
}

function createInfoItem(labelText, valueText) {
  const item = document.createElement("div");
  item.className = "shop-card__info-item";

  const label = document.createElement("span");
  label.className = "shop-card__info-label";
  label.textContent = labelText;

  const value = document.createElement("div");
  value.className = "shop-card__info-value";
  value.textContent = valueText;

  item.append(label, value);
  return item;
}

function animateExpand(card) {
  const summaryBtn = card.querySelector(".shop-card__summary");
  const details = card.querySelector(".shop-card__details");
  const inner = card.querySelector(".shop-card__details-inner");

  card.classList.add("is-expanded");
  summaryBtn.setAttribute("aria-expanded", "true");
  details.setAttribute("aria-hidden", "false");

  if (prefersReducedMotion()) {
    details.style.height = "auto";
    return;
  }

  // Start collapsed -> expand to measured height for a smooth transition.
  details.style.height = "0px";
  // Force reflow to ensure the browser picks up the starting height.
  void details.offsetHeight;

  details.style.height = `${inner.scrollHeight}px`;

  const onEnd = event => {
    if (event.target !== details || event.propertyName !== "height") return;
    details.removeEventListener("transitionend", onEnd);
    // Allow content to grow naturally after the animation.
    if (card.classList.contains("is-expanded")) {
      details.style.height = "auto";
    }
  };

  details.addEventListener("transitionend", onEnd);
}

function animateCollapse(card) {
  const summaryBtn = card.querySelector(".shop-card__summary");
  const details = card.querySelector(".shop-card__details");

  summaryBtn.setAttribute("aria-expanded", "false");

  if (prefersReducedMotion()) {
    card.classList.remove("is-expanded");
    details.setAttribute("aria-hidden", "true");
    details.style.height = "0px";
    return;
  }

  // If height is "auto", lock it to the current pixel height before collapsing.
  details.style.height = `${details.scrollHeight}px`;
  void details.offsetHeight;

  card.classList.remove("is-expanded");
  details.style.height = "0px";

  const onEnd = event => {
    if (event.target !== details || event.propertyName !== "height") return;
    details.removeEventListener("transitionend", onEnd);
    // Keep content accessible only when expanded.
    if (!card.classList.contains("is-expanded")) {
      details.setAttribute("aria-hidden", "true");
    }
  };

  details.addEventListener("transitionend", onEnd);
}

function toggleCard(card) {
  const isExpanded = card.classList.contains("is-expanded");

  // Only one expanded at a time.
  if (expandedCard && expandedCard !== card) {
    animateCollapse(expandedCard);
    expandedCard = null;
  }

  if (isExpanded) {
    animateCollapse(card);
    expandedCard = null;
    return;
  }

  animateExpand(card);
  expandedCard = card;
}

function createShopCard(shop) {
  const shopId = shop?.id ?? "-";
  const isOpen = Boolean(shop?.accepting_orders);

  // Placeholders (frontend-only).
  const name = shop.shop_name || "Shop";
  const description = "Professional printing services available.";
  const contact = shop.phone || "-";
  const address = shop.address || "-";


  const card = document.createElement("article");
  card.className = "shop-card";
  card.style.setProperty("--shop-hue", String(computeHue(shopId)));

  const detailsId = `shop-details-${shopId}`;

  // Summary (collapsed) button: clicking expands/collapses the card.
  const summaryBtn = document.createElement("button");
  summaryBtn.type = "button";
  summaryBtn.className = "shop-card__summary";
  summaryBtn.setAttribute("aria-expanded", "false");
  summaryBtn.setAttribute("aria-controls", detailsId);
  summaryBtn.addEventListener("click", () => toggleCard(card));

  const media = document.createElement("div");
  media.className = "shop-card__media";
  media.setAttribute("aria-hidden", "true");

  const main = document.createElement("div");
  main.className = "shop-card__main";

  const top = document.createElement("div");
  top.className = "shop-card__top";

  const title = document.createElement("h3");
  title.className = "shop-card__title";
  title.textContent = name;

  const tag = document.createElement("span");
  tag.className = `shop-card__tag ${isOpen ? "is-open" : "is-busy"}`;
  tag.textContent = isOpen ? "Accepting Orders" : "Busy";

  top.append(title, tag);

  const desc = document.createElement("p");
  desc.className = "shop-card__desc";
  desc.textContent = description;

  const meta = document.createElement("div");
  meta.className = "shop-card__meta";

  const metaAvg = document.createElement("span");
  metaAvg.className = "shop-card__meta-item";
  metaAvg.textContent = `Avg: ${formatAvgTime(shop?.avg_print_time_per_page)}`;

  const metaLoc = document.createElement("span");
  metaLoc.className = "shop-card__meta-item";
  metaLoc.textContent = address;

  meta.append(metaAvg, metaLoc);
  main.append(top, desc, meta);

  const chevron = document.createElement("div");
  chevron.className = "shop-card__chevron";
  chevron.setAttribute("aria-hidden", "true");

  summaryBtn.append(media, main, chevron);

  // Details (expanded content) - starts collapsed (height controlled by JS).
  const details = document.createElement("div");
  details.className = "shop-card__details";
  details.id = detailsId;
  details.setAttribute("aria-hidden", "true");
  details.setAttribute("role", "region");
  details.setAttribute("aria-label", `${name} details`);

  const inner = document.createElement("div");
  inner.className = "shop-card__details-inner";

  const infoGrid = document.createElement("div");
  infoGrid.className = "shop-card__info-grid";
  infoGrid.append(
    createInfoItem("Contact", contact),
    createInfoItem("Shop ID", String(shopId)),
    createInfoItem("Avg time / page", formatAvgTime(shop?.avg_print_time_per_page))
  );

  const pricing = document.createElement("div");
  pricing.className = "shop-card__pricing";

  const pricingTitle = document.createElement("div");
  pricingTitle.className = "shop-card__section-title";
  pricingTitle.textContent = "Service pricing";

  pricing.append(pricingTitle);
  PRICING.forEach(row => {
    const rowEl = document.createElement("div");
    rowEl.className = "shop-card__pricing-row";

    const left = document.createElement("span");
    left.textContent = row.label;

    const right = document.createElement("span");
    right.textContent = row.value;

    rowEl.append(left, right);
    pricing.append(rowEl);
  });

  const actions = document.createElement("div");
  actions.className = "shop-card__actions";

  const hint = document.createElement("div");
  hint.className = "shop-card__hint";
  hint.textContent = isOpen ? "Tap Place Order to continue." : "This shop is busy right now.";

  const orderBtn = document.createElement("button");
  orderBtn.type = "button";
  orderBtn.className = "btn primary shop-card__order-btn";
  orderBtn.textContent = "Place Order";
  orderBtn.disabled = !isOpen;
  orderBtn.addEventListener("click", event => {
    event.preventDefault();
    event.stopPropagation();
    window.location.href = `order.html?shop_id=${encodeURIComponent(shopId)}`;
  });

  actions.append(hint, orderBtn);

  inner.append(infoGrid, pricing, actions);
  details.append(inner);

  card.append(summaryBtn, details);
  return card;
}

function renderShops(shops) {
  if (!Array.isArray(shops) || shops.length === 0) {
    shopGrid.innerHTML = "";
    shopState.textContent = "No shops available.";
    return;
  }

  expandedCard = null;
  shopGrid.innerHTML = "";
  shopState.textContent = "";

  shops.forEach(shop => {
    shopGrid.appendChild(createShopCard(shop));
  });
}

function loadShops() {
  shopState.textContent = "Loading shops...";

  api.get("/shops")
    .then(res => renderShops(res.data))
    .catch(() => {
      shopGrid.innerHTML = "";
      shopState.textContent = "Failed to load shops.";
    });
}

loadShops();

