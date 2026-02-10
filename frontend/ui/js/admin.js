const adminApi = axios.create({
  baseURL: "http://127.0.0.1:8000",
});

const SHOP_KEY = "PRINTMATE_SHOP_ID";
const ROLE_KEY = "PRINTMATE_ROLE";

function getQueryParam(key) {
  try {
    return new URLSearchParams(window.location.search).get(key);
  } catch (err) {
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
  if (role === "SUPER_ADMIN") {
    return null;
  }

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

window.setAdminContext = function () {
  const roleInput = window.prompt("Enter role (ADMIN or SUPER_ADMIN)") || "";
  const role = normalizeRole(roleInput) || "ADMIN";
  localStorage.setItem(ROLE_KEY, role);

  if (role === "SUPER_ADMIN") {
    localStorage.removeItem(SHOP_KEY);
  } else {
    const shopId = window.prompt("Enter your Shop ID") || "";
    if (shopId) {
      localStorage.setItem(SHOP_KEY, shopId);
    }
  }

  window.location.reload();
};

adminApi.interceptors.request.use(config => {
  const role = resolveRole();
  const shopId = resolveShopId(role);

  config.headers["X-ROLE"] = role;
  if (shopId) {
    config.headers["X-SHOP-ID"] = shopId;
  }

  return config;
});
