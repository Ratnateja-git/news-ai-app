// Same-origin is the default for local FastAPI and Render. Set this before
// loading the app scripts only when serving the UI from a separate origin.
window.priyaApiUrl = (path) => `${window.PRIYA_API_BASE_URL || ""}${path}`;
