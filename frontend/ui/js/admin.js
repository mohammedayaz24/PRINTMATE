const adminClient = window.api || axios.create({
  baseURL: "http://127.0.0.1:8000"
});

if (typeof window !== "undefined") {
  window.api = window.api || adminClient;
  window.adminApi = window.adminApi || adminClient;
}

const SHOP_KEY = "PRINTMATE_SHOP_ID";
const ROLE_KEY = "PRINTMATE_ROLE";

function getQueryParam(key) {
  try {
    return new URLSearchParams(window.location.search).get(key);
  } catch {
    return null;
  }
}

function normalizeRole(role) {
  return (role || "").toString().trim().toUpperCase();
}

function resolveRole() {
  const paramRole = normalizeRole(getQueryParam("role"));

  if (paramRole) {
    localStorage.setItem(ROLE_KEY, paramRole);
    return paramRole;
  }

  const storedRole = localStorage.getItem(ROLE_KEY);
  return storedRole ? normalizeRole(storedRole) : "ADMIN";
}

function resolveShopId(role) {
  if (role === "SUPER_ADMIN") return null;

  const paramShop = getQueryParam("shop_id") || getQueryParam("shopId");

  if (paramShop) {
    localStorage.setItem(SHOP_KEY, paramShop);
    return paramShop;
  }

  let shopId = localStorage.getItem(SHOP_KEY);

  if (!shopId) {
    shopId = window.prompt("Enter your Shop ID") || "";
    if (shopId) {
      localStorage.setItem(SHOP_KEY, shopId);
    }
  }

  return shopId || null;
}

adminClient.interceptors.request.use(config => {
  const role = resolveRole() || "ADMIN";
  const shopId = resolveShopId(role);

  // Ensure headers object exists
  config.headers = config.headers || {};

  config.headers["X-ROLE"] = role;

  if (shopId) {
    config.headers["X-SHOP-ID"] = shopId;
  }

  return config;
});

