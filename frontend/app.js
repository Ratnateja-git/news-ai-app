// ======================================================
// PRIYA AI
// UI Controller
// Voice + chat logic lives in voice.js.
// This file owns: the live clock and the theme switcher.
// ======================================================

// ---------------- DOM ----------------

const clock = document.querySelector("#clock");


// ======================================================
// LIVE CLOCK
// ======================================================

function updateClock() {

    if (!clock) return;

    clock.textContent = new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit"
    });

}

updateClock();
setInterval(updateClock, 1000);


// ======================================================
// THEME SWITCHER
// Dark (default) / Light / System, remembered per browser.
// ======================================================

const THEME_KEY = "priya-theme";

const themeToggle = document.querySelector("#theme-toggle");
const themeButtons = themeToggle
    ? Array.from(themeToggle.querySelectorAll("[data-theme-choice]"))
    : [];

const systemPrefersDark =
    window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)");

function resolveTheme(choice) {

    if (choice === "system") {
        return systemPrefersDark && systemPrefersDark.matches ? "dark" : "light";
    }

    return choice === "light" ? "light" : "dark";
}

function applyTheme(choice) {

    const resolved = resolveTheme(choice);

    document.documentElement.setAttribute("data-theme", resolved);

    themeButtons.forEach((button) => {
        button.classList.toggle(
            "active",
            button.dataset.themeChoice === choice
        );
    });
}

function setTheme(choice) {

    try {
        localStorage.setItem(THEME_KEY, choice);
    } catch (error) {
        // Storage may be unavailable (private browsing, etc). Theme just
        // won't persist across reloads — not fatal.
    }

    applyTheme(choice);
}

// Initialize toggle UI to match whatever the inline <head> script already
// set on <html data-theme="..."> before first paint.
(function initTheme() {

    let saved = "dark";

    try {
        saved = localStorage.getItem(THEME_KEY) || "dark";
    } catch (error) {
        saved = "dark";
    }

    applyTheme(saved);

})();

themeButtons.forEach((button) => {
    button.addEventListener("click", () => {
        setTheme(button.dataset.themeChoice);
    });
});

// If the user picked "system", keep following the OS setting live.
if (systemPrefersDark && systemPrefersDark.addEventListener) {

    systemPrefersDark.addEventListener("change", () => {

        let saved = "dark";

        try {
            saved = localStorage.getItem(THEME_KEY) || "dark";
        } catch (error) {
            saved = "dark";
        }

        if (saved === "system") {
            applyTheme("system");
        }
    });
}