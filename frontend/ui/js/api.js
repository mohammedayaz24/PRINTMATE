const api = axios.create({
  baseURL: "http://127.0.0.1:8000",
});

const STUDENT_KEY = "PRINTMATE_STUDENT_ID";

function getQueryParam(key) {
  try {
    return new URLSearchParams(window.location.search).get(key);
  } catch (err) {
    return null;
  }
}

function resolveStudentId() {
  const paramId = getQueryParam("student_id") || getQueryParam("studentId");
  if (paramId) {
    localStorage.setItem(STUDENT_KEY, paramId);
    return paramId;
  }

  let stored = localStorage.getItem(STUDENT_KEY);
  if (!stored) {
    stored = window.prompt("Enter your Student ID") || "";
    if (stored) {
      localStorage.setItem(STUDENT_KEY, stored);
    }
  }

  return stored;
}

const STUDENT_ID = resolveStudentId();
window.STUDENT_ID = STUDENT_ID;

api.interceptors.request.use(config => {
  if (STUDENT_ID) {
    config.headers["X-STUDENT-ID"] = STUDENT_ID;
  }
  return config;
});
