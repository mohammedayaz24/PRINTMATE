const api = axios.create({
  baseURL: "http://127.0.0.1:8000"
});

function isAdminContext() {
  if (typeof window !== "undefined" && window.IS_ADMIN) return true;
  if (typeof document !== "undefined") {
    const body = document.body;
    if (body?.classList?.contains("admin")) {
      return true;
    }
  }
  return false;
}

if (typeof window !== "undefined") {
  window.api = window.api || api;
}

const STUDENT_KEY = "PRINTMATE_STUDENT_ID";

// -----------------------------
// Get student id from URL or storage
// -----------------------------
function getQueryParam(key) {
  try {
    return new URLSearchParams(window.location.search).get(key);
  } catch {
    return null;
  }
}

function resolveStudentId() {
  const paramId =
    getQueryParam("student_id") || getQueryParam("studentId");

  if (paramId) {
    localStorage.setItem(STUDENT_KEY, paramId);
    return paramId;
  }

  const stored = localStorage.getItem(STUDENT_KEY);

  if (!stored) {
    if (!isAdminContext()) {
      alert("Student ID not found. Please login again.");
    }
    return null;
  }

  return stored;
}

const STUDENT_ID = resolveStudentId();
window.STUDENT_ID = STUDENT_ID;

// -----------------------------
// Attach Header to every request
// -----------------------------
api.interceptors.request.use(config => {
  if (STUDENT_ID) {
    config.headers["X-STUDENT-ID"] = STUDENT_ID;  // ✅ dynamic
  }
  return config;
});
