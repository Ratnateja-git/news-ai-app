// ============================================================
// PRIYA VOICE.JS
// Kokoro TTS + Browser Speech Recognition
// Qwen3 remains responsible for news answers.
// ============================================================

let recognition = null;
let currentAudio = null;
let stopped = false;
let isListening = false;
let activeAskController = null;
let ttsUnavailable = false;
let activeTtsController = null;
let currentAudioUrl = null;
let resolveCurrentPlayback = null;
let speechRunId = 0;
let chatScrollFrame = 0;
let shouldFollowChat = true;
let selectedImage = null;
let previewUrl = null;


// ============================================================
// DOM ELEMENTS
// ============================================================


const statusElement =
    document.querySelector("#status");

const questionInput =
    document.querySelector("#question");

const chatContainer =
    document.querySelector("#chat-window");

const jumpToLatestButton =
    document.querySelector("#jump-to-latest");

const thinkingIndicator =
    document.querySelector("#thinking-indicator");

const refreshButton =
    document.querySelector("#refresh");

const refreshMarketButton =
    document.querySelector("#refresh-market");

const clearChatButton =
    document.querySelector("#clear-chat");

const headlinesElement =
    document.querySelector("#headlines");

const marketElement =
    document.querySelector("#market-grid");

const answerElement =
    document.querySelector("#answer");

const questionDisplay =
    document.querySelector("#question-display");

const categoryDisplay =
    document.querySelector("#detected-category");

const imageUpload = document.querySelector("#image-upload");
const attachImageButton = document.querySelector("#attach-image");
const imagePreview = document.querySelector("#image-preview");
const imagePreviewImage = document.querySelector("#image-preview-img");
const removeImageButton = document.querySelector("#remove-image");
const sendButton = document.querySelector('[form="question-form"]');


// ============================================================
// ORB STATE MACHINE
// idle | listening | thinking | speaking | offline
// Driving this off document.body classes keeps styles.css fully
// in charge of what each state actually looks like.
// ============================================================

const ORB_STATES = ["idle", "listening", "thinking", "speaking", "offline"];

function setOrbState(state) {

    if (!ORB_STATES.includes(state)) {
        state = "idle";
    }

    // State belongs on the document root, never on <body>. This prevents a
    // component selector such as .thinking from accidentally matching the
    // page itself and changing the global layout during a request.
    document.documentElement.dataset.orbState = state;
    document.body.classList.remove(...ORB_STATES);
}

// Start in idle.
setOrbState("idle");


// ============================================================
// CHAT UI HELPERS
// ============================================================

function isNearChatBottom() {
    if (!chatContainer) return true;
    return chatContainer.scrollTop + chatContainer.clientHeight >= chatContainer.scrollHeight - 80;
}


function updateJumpToLatestControl() {

    if (!jumpToLatestButton) return;

    jumpToLatestButton.classList.toggle(
        "hidden",
        shouldFollowChat
    );
}


function scrollChat(force = false) {

    if (!force && !shouldFollowChat) {
        updateJumpToLatestControl();
        return;
    }

    if (chatScrollFrame) {
        cancelAnimationFrame(chatScrollFrame);
    }

    chatScrollFrame = requestAnimationFrame(() => {
        if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
        chatScrollFrame = 0;
        updateJumpToLatestControl();
    });
}


chatContainer?.addEventListener("scroll", () => {

    if (chatScrollFrame) return;

    chatScrollFrame = requestAnimationFrame(() => {
        shouldFollowChat = isNearChatBottom();
        updateJumpToLatestControl();
        chatScrollFrame = 0;
    });

}, { passive: true });


if (jumpToLatestButton) {

    jumpToLatestButton.addEventListener("click", () => {
        shouldFollowChat = true;
        if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
        updateJumpToLatestControl();
    });
}


function uiThinking(show = true) {

    if (thinkingIndicator) {
        thinkingIndicator.classList.add("hidden");
    }

    if (show) {
        setOrbState("thinking");
    }

    shouldFollowChat = isNearChatBottom();
    if (shouldFollowChat) scrollChat();
}


function formatTime(date = new Date()) {

    return date.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit"
    });
}


function escapeHtml(value) {

    const div =
        document.createElement("div");

    div.textContent = value || "";

    return div.innerHTML;
}


// Small, safe markdown-ish renderer: escapes everything first, then
// re-introduces a handful of common patterns (code blocks, inline code,
// bullet lists, paragraphs). Never trusts raw HTML from the model.
function renderRichText(rawText) {

    const text = String(rawText || "");

    const codeBlocks = [];

    // Pull out fenced code blocks first so their contents are never
    // treated as list items or paragraphs.
    const withoutFences = text.replace(/```([\s\S]*?)```/g, (match, code) => {
        const token = `@@CODEBLOCK_${codeBlocks.length}@@`;
        codeBlocks.push(escapeHtml(code.trim()));
        return token;
    });

    const escaped = escapeHtml(withoutFences);

    const lines = escaped.split("\n");

    let html = "";
    let inList = false;

    lines.forEach((line) => {

        const trimmed = line.trim();

        const isBullet = /^[-*•]\s+/.test(trimmed);

        if (isBullet) {

            if (!inList) {
                html += "<ul>";
                inList = true;
            }

            html += `<li>${trimmed.replace(/^[-*•]\s+/, "")}</li>`;

        } else {

            if (inList) {
                html += "</ul>";
                inList = false;
            }

            if (trimmed) {
                html += `<p>${trimmed.replace(/`([^`]+)`/g, "<code>$1</code>")}</p>`;
            }
        }
    });

    if (inList) {
        html += "</ul>";
    }

    codeBlocks.forEach((code, index) => {
        html = html.replace(
            `@@CODEBLOCK_${index}@@`,
            `<pre><code>${code}</code></pre>`
        );
    });

    return html || `<p>${escapeHtml(text)}</p>`;
}


function createMessage(type, text, metaParts = []) {

    const bubbleType =
        type === "user" ? "user" : "ai";

    const message =
        document.createElement("div");

    message.className =
        `message ${bubbleType}`;

    const chips = (metaParts || [])
        .filter(Boolean)
        .map((part) => `<span class="meta-chip">${escapeHtml(part)}</span>`)
        .join("");

    message.innerHTML = `

        <div class="avatar">

            ${bubbleType === "user" ? "You" : "AI"}

        </div>

        <div class="bubble">

            <div class="message-content">

                ${bubbleType === "user" ? escapeHtml(text) : renderRichText(text)}

            </div>

            <span class="message-meta">
                <span>${formatTime()}</span>
                ${chips}
            </span>

        </div>

    `;

    return message;
}


function uiAddUser(text) {

    if (!chatContainer) return;

    shouldFollowChat = true;

    chatContainer.appendChild(
        createMessage(
            "user",
            text
        )
    );

    scrollChat(true);
}


function uiAddUserImage(file, text) {

    if (!chatContainer || !file) return;

    const message = createMessage("user", text || "Image");
    const content = message.querySelector(".message-content");
    const image = document.createElement("img");
    image.className = "user-image";
    image.alt = "Uploaded image";
    image.src = URL.createObjectURL(file);
    image.addEventListener("load", () => URL.revokeObjectURL(image.src), { once: true });
    content.prepend(image);
    chatContainer.appendChild(message);
    shouldFollowChat = true;
    scrollChat(true);
}


function uiAddImageResults(message, results) {

    if (!message || !Array.isArray(results) || !results.length) return;

    const content = message.querySelector(".message-content");
    if (!content) return;

    const heading = document.createElement("p");
    heading.textContent = "Images";
    const grid = document.createElement("div");
    grid.className = "image-results";

    results.forEach((result) => {
        if (!result?.image_url || !result?.source_url) return;
        const link = document.createElement("a");
        link.className = "image-result";
        link.href = result.source_url;
        link.target = "_blank";
        link.rel = "noreferrer";
        const image = document.createElement("img");
        image.src = result.image_url;
        image.alt = result.title || "Image result";
        image.addEventListener("error", () => link.remove(), { once: true });
        const title = document.createElement("span");
        title.textContent = result.title || result.source || "Image result";
        link.append(image, title);
        grid.appendChild(link);
    });

    if (grid.childElementCount) content.append(heading, grid);
}


function clearSelectedImage() {

    selectedImage = null;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    if (imageUpload) imageUpload.value = "";
    if (imagePreviewImage) imagePreviewImage.removeAttribute("src");
    imagePreview?.classList.add("hidden");
}


function setComposerBusy(isBusy) {

    if (questionInput) questionInput.disabled = isBusy;
    if (attachImageButton) attachImageButton.disabled = isBusy;
    if (sendButton) sendButton.disabled = isBusy;
}


if (attachImageButton && imageUpload) {
    attachImageButton.addEventListener("click", () => imageUpload.click());
    imageUpload.addEventListener("change", () => {
        const file = imageUpload.files?.[0];
        if (!file) return;
        if (!/^image\/(jpeg|png|webp)$/i.test(file.type)) {
            clearSelectedImage();
            setStatus("Please choose a JPG, PNG, or WEBP image.");
            return;
        }
        clearSelectedImage();
        selectedImage = file;
        previewUrl = URL.createObjectURL(file);
        if (imagePreviewImage) imagePreviewImage.src = previewUrl;
        imagePreview?.classList.remove("hidden");
        questionInput?.focus();
    });
}

removeImageButton?.addEventListener("click", clearSelectedImage);


function uiAddAssistant(
    text,
    metaParts = []
) {

    if (!chatContainer) return;

    const followPage = isNearChatBottom();
    shouldFollowChat = followPage;

    const message = createMessage(
        "assistant",
        text,
        Array.isArray(metaParts) ? metaParts : [metaParts]
    );

    chatContainer.appendChild(message);

    if (followPage) scrollChat();

    return message;
}


function uiUpdateAssistant(message, text, metaParts = []) {

    const content = message?.querySelector(".message-content");
    const meta = message?.querySelector(".message-meta");

    if (!content || !meta) return;

    const followPage = isNearChatBottom();
    shouldFollowChat = followPage;
    const chips = (Array.isArray(metaParts) ? metaParts : [metaParts])
        .filter(Boolean)
        .map((part) => `<span class="meta-chip">${escapeHtml(part)}</span>`)
        .join("");

    content.innerHTML = renderRichText(text);
    meta.innerHTML = `<span>${formatTime()}</span>${chips}`;

    if (followPage) scrollChat();
}


function normaliseVisionAnswer(answer, description = "") {

    let text = String(answer || "").trim();
    const fenced = text.match(/^\s*```(?:json)?\s*\n?([\s\S]*?)\n?```\s*$/i);
    if (fenced) text = fenced[1].trim();

    try {
        const payload = JSON.parse(text);
        if (payload && typeof payload === "object" && !Array.isArray(payload)) {
            return String(payload.answer || payload.description || description || "").trim();
        }
    } catch (error) {
        // The backend already handles malformed JSON. This is a defensive
        // UI fallback for a stale server response or an unusual model reply.
    }

    const getField = (name) => {
        const match = text.match(new RegExp(`['\\"]?${name}['\\"]?\\s*:\\s*\\"((?:\\\\.|[^\\"])*)\\"`, "i"));
        if (!match) return "";
        try {
            return JSON.parse(`"${match[1]}"`).trim();
        } catch (error) {
            return match[1].replace(/\\"/g, "\"").trim();
        }
    };

    const extracted = getField("answer") || getField("description");
    if (extracted) return extracted;
    if (/^\s*[\[{]/.test(text)) return String(description || "").trim();
    return text.replace(/^\s*priya\s*:\s*/i, "").trim() || String(description || "").trim();
}

// ============================================================
// STATUS
// ============================================================

function setStatus(message) {

    if (statusElement) {
        statusElement.textContent = message;
    }
}


// ============================================================
// WAKE PHRASE
// ============================================================

function stripWakePhrase(text) {

    if (!text) {
        return "";
    }

    return text
        .replace(
            /^\s*(?:hey|hi)\s+priya[\s,!]*/i,
            ""
        )
        .replace(
            /^\s*priya[\s,!]*/i,
            ""
        )
        .trim();
}


// ============================================================
// CHECK IF USER ONLY SAID "HEY PRIYA"
// ============================================================

function isWakeOnly(text) {

    if (!text) {
        return false;
    }

    return /^(?:(?:hey|hi)\s+)?priya[\s,!]*$/i
        .test(text.trim());
}


// ============================================================
// STOP KOKORO AUDIO
// ============================================================

function stopAudio() {

    stopped = true;

    speechRunId += 1;

    if (activeTtsController) {
        activeTtsController.abort();
        activeTtsController = null;
    }

    if (currentAudio) {

        try {
            currentAudio.pause();
            currentAudio.currentTime = 0;
        } catch (error) {
            console.warn(
                "Could not stop audio:",
                error
            );
        }

        currentAudio = null;
    }

    if (resolveCurrentPlayback) {
        resolveCurrentPlayback();
        resolveCurrentPlayback = null;
    }

    if (currentAudioUrl) {
        URL.revokeObjectURL(currentAudioUrl);
        currentAudioUrl = null;
    }
}


// ============================================================
// PLAY KOKORO AUDIO
// ============================================================

async function speakLegacy(text) {

    // Kept only for compatibility with any old console call. Route it through
    // the production queue so there is never a second TTS fetch path.
    return speak(text);

    if (!text || !text.trim()) {
        return;
    }

    stopped = false;

    // Stop previous audio.
    stopAudio();

    stopped = false;

    setStatus(
        "🔊 Priya is speaking..."
    );

    setOrbState("speaking");

    const waveElement = document.querySelector("#wave");

    try {

        const response = await fetch(
            "/tts",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    // Kept only as an internal fallback while the queue below
                    // owns all production speech. Never post a full answer.
                    text: splitSpeechSentences(text)[0] || text.trim()
                })
            }
        );


        // ----------------------------------------------------
        // Check server response
        // ----------------------------------------------------

        if (!response.ok) {

            let errorMessage =
                "Kokoro could not generate speech.";

            try {

                const errorData =
                    await response.json();

                if (errorData.detail) {
                    errorMessage =
                        errorData.detail;
                }

            } catch {
                // Response was not JSON.
            }

            throw new Error(
                errorMessage
            );
        }


        // ----------------------------------------------------
        // Convert WAV response to Blob
        // ----------------------------------------------------

        const audioBlob =
            await response.blob();


        if (!audioBlob.size) {

            throw new Error(
                "Kokoro returned empty audio."
            );
        }


        // ----------------------------------------------------
        // Create temporary audio URL
        // ----------------------------------------------------

        const audioUrl =
            URL.createObjectURL(
                audioBlob
            );


        const audio =
            new Audio(audioUrl);


        currentAudio = audio;


        // ----------------------------------------------------
        // Audio events
        // ----------------------------------------------------

        audio.onplay = () => {

            setOrbState("speaking");

            if (waveElement) {
                waveElement.classList.remove("hidden");
            }

            setStatus("Priya is speaking...");
        };


        audio.onended = () => {

            if (waveElement) {
                waveElement.classList.add("hidden");
            }

            URL.revokeObjectURL(
                audioUrl
            );

            if (currentAudio === audio) {
                currentAudio = null;
            }

            if (!stopped) {

                setStatus(
                    "Ready"
                );

                setOrbState("idle");
            }
        };


        audio.onerror = (event) => {

            console.error(
                "Kokoro audio playback error:",
                event
            );

            if (waveElement) {
                waveElement.classList.add("hidden");
            }

            URL.revokeObjectURL(
                audioUrl
            );

            if (currentAudio === audio) {
                currentAudio = null;
            }

            setStatus(
                "Priya voice could not be played."
            );

            setOrbState("offline");
        };


        // ----------------------------------------------------
        // Play Kokoro voice
        // ----------------------------------------------------

        await audio.play();

    } catch (error) {

        console.error(
            "Kokoro TTS error:",
            error
        );

        if (waveElement) {
            waveElement.classList.add("hidden");
        }

        setStatus(
            "Priya voice could not be played."
        );

        setOrbState("offline");
    }
}


const FIRST_TTS_CHUNK_MAX = 100;
const SUBSEQUENT_TTS_CHUNK_MAX = 160;
const FIRST_TTS_CHUNK_PREFERRED_MIN = 50;


function splitLongSpeechSegment(segment, maxLength) {

    const parts = [];
    let remaining = segment.trim();

    while (remaining.length > maxLength) {
        const preview = remaining.slice(0, maxLength + 1);
        const naturalBoundary = Math.max(
            preview.lastIndexOf(","),
            preview.lastIndexOf(";"),
            preview.lastIndexOf(":")
        );
        const wordBoundary = preview.lastIndexOf(" ");
        const boundary = naturalBoundary >= Math.floor(maxLength * 0.55)
            ? naturalBoundary + 1
            : wordBoundary;

        // A single unusually long word is still sent intact.
        if (boundary <= 0) break;

        parts.push(remaining.slice(0, boundary).trim());
        remaining = remaining.slice(boundary).trim();
    }

    if (remaining) {
        parts.push(remaining);
    }

    return parts;
}


function splitSpeechChunks(text) {

    const sentences = String(text || "")
        .trim()
        .match(/[^.!?]+[.!?]+|[^.!?]+$/g)
        ?.map((sentence) => sentence.trim())
        .filter(Boolean) || [];

    if (!sentences.length) return [];

    const firstSentenceParts = splitLongSpeechSegment(
        sentences.shift(),
        FIRST_TTS_CHUNK_MAX
    );
    let firstChunk = firstSentenceParts.shift() || "";
    const remainingSegments = [
        ...firstSentenceParts,
        ...sentences.flatMap((sentence) =>
            splitLongSpeechSegment(sentence, SUBSEQUENT_TTS_CHUNK_MAX)
        )
    ];

    // A very short opener sounds more natural when followed by the next
    // complete short segment, while still keeping the first request small.
    if (
        firstChunk.length < FIRST_TTS_CHUNK_PREFERRED_MIN &&
        remainingSegments.length &&
        firstChunk.length + 1 + remainingSegments[0].length <= FIRST_TTS_CHUNK_MAX
    ) {
        firstChunk = firstChunk + " " + remainingSegments.shift();
    }

    const chunks = firstChunk ? [firstChunk] : [];
    let currentChunk = "";

    for (const segment of remainingSegments) {
        const candidate = currentChunk
            ? currentChunk + " " + segment
            : segment;

        if (currentChunk && candidate.length > SUBSEQUENT_TTS_CHUNK_MAX) {
            chunks.push(currentChunk);
            currentChunk = segment;
        } else {
            currentChunk = candidate;
        }
    }

    if (currentChunk) {
        chunks.push(currentChunk);
    }

    return chunks;
}


async function requestSpeechAudio(text, controller, timing = null, chunkNumber = null) {

    if (timing && !timing.firstTtsStartedAt) {
        timing.firstTtsStartedAt = performance.now();
        console.log("[PERF][VOICE] first TTS request");
    }

    const response = await fetch("/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            text,
            chunk: chunkNumber
        }),
        signal: controller.signal
    });

    if (timing && !timing.firstTtsResponseAt) {
        timing.firstTtsResponseAt = performance.now();
        console.log(
            "[PERF][VOICE] first audio received: " +
            ((timing.firstTtsResponseAt - timing.firstTtsStartedAt) / 1000).toFixed(3) +
            "s"
        );
    }

    if (!response.ok) {
        let detail = "Kokoro could not generate speech.";
        try {
            detail = (await response.json()).detail || detail;
        } catch {
            // Keep the general message for a non-JSON error response.
        }
        throw new Error(detail);
    }

    const audioBlob = await response.blob();
    if (!audioBlob.size) {
        throw new Error("Kokoro returned empty audio.");
    }

    return audioBlob;
}


function playSpeechAudio(audioBlob, runId, timing = null, chunkNumber = null) {

    return new Promise((resolve, reject) => {
        if (runId !== speechRunId) {
            resolve();
            return;
        }

        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        const waveElement = document.querySelector("#wave");
        let settled = false;

        const cleanup = () => {
            if (settled) return;
            settled = true;
            URL.revokeObjectURL(audioUrl);
            if (currentAudio === audio) currentAudio = null;
            if (currentAudioUrl === audioUrl) currentAudioUrl = null;
            if (resolveCurrentPlayback === finishPlayback) {
                resolveCurrentPlayback = null;
            }
        };

        const finishPlayback = () => {
            cleanup();
            resolve();
        };

        currentAudio = audio;
        currentAudioUrl = audioUrl;
        resolveCurrentPlayback = finishPlayback;

        audio.onplay = () => {
            setOrbState("speaking");
            waveElement?.classList.remove("hidden");
            setStatus("Priya is speaking...");
            console.log("[PERF][VOICE] chunk " + chunkNumber + " playback");

            if (timing && !timing.firstAudioStartedAt) {
                timing.firstAudioStartedAt = performance.now();
                const afterTts = timing.firstTtsResponseAt
                    ? (timing.firstAudioStartedAt - timing.firstTtsResponseAt) / 1000
                    : 0;
                const timeToFirstAudio =
                    (timing.firstAudioStartedAt - timing.submittedAt) / 1000;
                console.log(
                    "[PERF][VOICE] first audio playback: +" +
                    afterTts.toFixed(3) +
                    "s"
                );
                console.log(
                    "[PERF][VOICE] TIME TO FIRST AUDIO: " +
                    timeToFirstAudio.toFixed(3) +
                    "s"
                );
            }
        };

        audio.onended = () => {
            finishPlayback();
        };

        audio.onerror = () => {
            cleanup();
            reject(new Error("Kokoro audio playback failed."));
        };

        audio.play().catch((error) => {
            cleanup();
            reject(error);
        });
    });
}


async function speak(text, timing = null) {

    if (ttsUnavailable) {
        setStatus("Voice output is unavailable on this deployment.");
        return false;
    }

    const chunks = splitSpeechChunks(text);
    if (!chunks.length) return false;

    console.log("[PERF][VOICE] chunk count: " + chunks.length);
    chunks.forEach((chunk, index) => {
        console.log(
            "[PERF][VOICE] chunk " + (index + 1) + " length: " + chunk.length
        );
    });

    stopAudio();
    stopped = false;
    const runId = speechRunId;
    const controller = new AbortController();
    activeTtsController = controller;
    const narrationStartedAt = performance.now();

    try {
        // Keep exactly one synthesis request in flight. Once a sentence is
        // ready, start playback immediately and synthesize the next sentence
        // during that playback. This is a producer/consumer queue without
        // concurrent Kokoro work or waiting for the whole answer.
        let nextAudio = requestSpeechAudio(
            chunks[0],
            controller,
            timing,
            1
        );

        for (let index = 0; index < chunks.length; index += 1) {
            const audioBlob = await nextAudio;
            if (runId !== speechRunId) return;

            const playback = playSpeechAudio(
                audioBlob,
                runId,
                index === 0 ? timing : null,
                index + 1
            );

            if (index + 1 < chunks.length) {
                nextAudio = requestSpeechAudio(
                    chunks[index + 1],
                    controller,
                    null,
                    index + 2
                );
            }

            await playback;
            if (runId !== speechRunId) return;
        }

        if (runId === speechRunId) {
            console.log(
                "[PERF][VOICE] total narration: " +
                ((performance.now() - narrationStartedAt) / 1000).toFixed(3) +
                "s"
            );
            document.querySelector("#wave")?.classList.add("hidden");
            setStatus("Ready");
            setOrbState("idle");
            return true;
        }
    } catch (error) {
        if (error.name === "AbortError" || runId !== speechRunId) return;
        console.error("Kokoro TTS error:", error);
        document.querySelector("#wave")?.classList.add("hidden");
        if (error.message === "Voice/TTS is unavailable in this deployment because the Kokoro model is not installed.") {
            ttsUnavailable = true;
            setStatus("Voice output is unavailable on this deployment.");
        } else {
            setStatus("Priya voice could not be played.");
        }
        setOrbState("offline");
        return false;
    } finally {
        if (activeTtsController === controller) {
            activeTtsController = null;
        }
    }
}

// Optional features use this exact Kokoro playback pipeline instead of
// creating a browser-speech or alternate TTS path.
window.priyaSpeak = speak;
window.priyaStopAudio = stopAudio;



// ============================================================
// GREET PRIYA
// ============================================================

async function greetPriya() {

    const greeting =
        "Hello, I'm Priya. How can I help you?";

    uiAddAssistant(
        greeting,
        ["Assistant"]
    );

    await speak(greeting);
}

// ============================================================
// ASK PRIYA
// ============================================================


async function askPriya(question) {

    const cleanQuestion = String(question || "").trim();
    const imageFile = selectedImage;

    if (!cleanQuestion && !imageFile) {

        await greetPriya();
        return;

    }

    if (!imageFile && isWakeOnly(cleanQuestion)) {

        await greetPriya();
        return;

    }

    const actualQuestion = imageFile ? cleanQuestion : stripWakePhrase(cleanQuestion);

    if (!actualQuestion && !imageFile) {

        await greetPriya();
        return;

    }

    const timing = {
        submittedAt: performance.now()
    };
    console.log("[PERF][VOICE] question submitted");

    // A new question always replaces any voice response still loading or
    // playing, so rapid requests cannot overlap.
    stopAudio();

    if (activeAskController) {
        activeAskController.abort();
    }

    const requestController = new AbortController();
    activeAskController = requestController;

    // ---------------------------
    // Add user bubble
    // ---------------------------

    if (imageFile) {
        uiAddUserImage(imageFile, cleanQuestion || "Describe this image");
        clearSelectedImage();
    } else {
        uiAddUser(cleanQuestion);
    }

    // clear input

    if (questionInput) {

        questionInput.value = "";

    }

    // show thinking animation

    uiThinking(true);

    setComposerBusy(true);

    setStatus(
        imageFile ? "Priya is looking at the image..." : "Priya is thinking..."
    );

    setOrbState("thinking");

    const assistantMessage = uiAddAssistant(
        imageFile ? "Priya is looking at the image..." : "Priya is thinking..."
    );

    try {

        timing.askStartedAt = performance.now();
        console.log("[PERF][VOICE] /ask started");
        let response;
        if (imageFile) {
            const formData = new FormData();
            formData.append("image", imageFile, imageFile.name);
            formData.append("question", actualQuestion);
            response = await fetch(
                window.priyaApiUrl
                    ? window.priyaApiUrl("/vision/analyze")
                    : "/vision/analyze",
                {
                method: "POST",
                body: formData,
                signal: requestController.signal
                }
            );
        } else {
            const askParams = new URLSearchParams({ question: actualQuestion });
            const activeInterviewQuestion = String(window.priyaActiveInterviewQuestion || "").trim();
            if (activeInterviewQuestion) {
                askParams.set("interview_question", activeInterviewQuestion);
            }
            const careerSessionId = String(window.priyaCareerSessionId || "").trim();
            if (careerSessionId) askParams.set("career_session_id", careerSessionId);
            const askPath = `/ask?${askParams.toString()}`;
            response = await fetch(
                window.priyaApiUrl
                    ? window.priyaApiUrl(askPath)
                    : askPath,
                { signal: requestController.signal }
            );
        }
        timing.askResponseAt = performance.now();
        console.log(
            "[PERF][VOICE] /ask completed: " +
            ((timing.askResponseAt - timing.askStartedAt) / 1000).toFixed(3) +
            "s"
        );

        const data = await response.json();

        if (!response.ok) {

            throw new Error(

                data.detail ||

                "Could not get response."

            );

        }

        if (activeAskController !== requestController) {
            return;
        }

        uiThinking(false);

        const visionAnswer = imageFile
            ? normaliseVisionAnswer(data.answer, data.description)
            : data.answer;
        const meta = imageFile ? ["image"] : [data.category, data.location, data.mode];

        uiUpdateAssistant(

            assistantMessage,

            visionAnswer,

            meta

        );
        if (imageFile) uiAddImageResults(assistantMessage, data.image_results);
        timing.answerRenderedAt = performance.now();
        console.log(
            "[PERF][VOICE] answer rendered: +" +
            ((timing.answerRenderedAt - timing.askResponseAt) / 1000).toFixed(3) +
            "s"
        );
        console.log("[PERF][VOICE] first sentence ready");

        // Text is already visible. Do not hold the request/UI lifecycle open
        // while Kokoro generates and plays its sentence queue.
        void speak(visionAnswer, timing);

    }

    catch(error){

        console.error(error);

        if (error.name === "AbortError" || activeAskController !== requestController) {
            return;
        }

        uiThinking(false);

        uiUpdateAssistant(

            assistantMessage,

            "Sorry, I couldn't get the latest news."

        );

        setStatus(

            "Error"

        );

        setOrbState("offline");

    }

    finally {

        if (activeAskController === requestController) {
            activeAskController = null;
        }
        setComposerBusy(false);

    }

}

// ============================================================
// SPEECH RECOGNITION
// ============================================================

function startPriya() {

    const Recognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;


    if (!Recognition) {

        setStatus(
            "Speech recognition is unavailable. Please use Chrome or Edge."
        );

        setOrbState("offline");

        return;
    }


    // --------------------------------------------------------
    // Stop any previous recognition
    // --------------------------------------------------------

    if (recognition) {

        try {
            recognition.stop();
        } catch {
            // Already stopped.
        }
    }


    // Stop current Kokoro audio.
    stopAudio();

    stopped = false;


    // --------------------------------------------------------
    // Create recognition
    // --------------------------------------------------------

    recognition =
        new Recognition();


    recognition.lang =
        "en-IN";


    recognition.interimResults =
        false;


    recognition.maxAlternatives =
        1;


    recognition.continuous =
        false;


    // --------------------------------------------------------
    // Recognition started
    // --------------------------------------------------------

    recognition.onstart = () => {

        isListening = true;

        setStatus(
            "Listening..."
        );

        setOrbState("listening");

        const waveElement = document.querySelector("#wave");

        if (waveElement) {
            waveElement.classList.remove("hidden");
        }
    };


    // --------------------------------------------------------
    // Recognition result
    // --------------------------------------------------------

    recognition.onresult =
        async (event) => {

            isListening = false;

            const waveElement = document.querySelector("#wave");

            if (waveElement) {
                waveElement.classList.add("hidden");
            }


            const said =
                event.results?.[0]?.[0]?.transcript
                ?.trim() || "";


            console.log(
                "Priya heard:",
                said
            );


            if (!said) {

                setStatus(
                    "I didn't hear anything. Please try again."
                );

                setOrbState("idle");

                return;
            }


            // ------------------------------------------------
            // If user only says "Hey Priya"
            // ------------------------------------------------

            if (isWakeOnly(said)) {

                await greetPriya();

                return;
            }


            // ------------------------------------------------
            // Ask actual question
            // ------------------------------------------------

            await askPriya(
                said
            );
        };


    // --------------------------------------------------------
    // Recognition ended
    // --------------------------------------------------------

    recognition.onend = () => {

        isListening = false;

        const waveElement = document.querySelector("#wave");

        if (waveElement) {
            waveElement.classList.add("hidden");
        }

        if (
            statusElement &&
            statusElement.textContent
                .includes("Listening")
        ) {

            setStatus(
                "Ready"
            );

            setOrbState("idle");
        }
    };


    // --------------------------------------------------------
    // Recognition error
    // --------------------------------------------------------

    recognition.onerror =
        (event) => {

            isListening = false;

            console.error(
                "Speech recognition error:",
                event.error
            );

            const waveElement = document.querySelector("#wave");

            if (waveElement) {
                waveElement.classList.add("hidden");
            }

            setOrbState("offline");

            switch (event.error) {

                case "not-allowed":

                    setStatus(
                        "Microphone permission is blocked."
                    );

                    break;


                case "no-speech":

                    setStatus(
                        "I didn't hear anything. Please try again."
                    );

                    break;


                case "audio-capture":

                    setStatus(
                        "Microphone could not be accessed."
                    );

                    break;


                case "network":

                    setStatus(
                        "Speech recognition network error."
                    );

                    break;


                default:

                    setStatus(
                        "Speech recognition failed. Please try again."
                    );
            }
        };


    // --------------------------------------------------------
    // Start microphone
    // --------------------------------------------------------

    try {

        recognition.start();

    } catch (error) {

        console.error(
            "Could not start recognition:",
            error
        );

        setStatus(
            "Priya is already listening."
        );
    }
}


// ============================================================
// STOP PRIYA
// ============================================================

function stopPriya() {

    stopped = true;

    // Stop microphone.
    if (recognition) {

        try {
            recognition.stop();
        } catch {
            // Already stopped.
        }
    }

    recognition = null;

    isListening = false;


    // Stop Kokoro audio.
    stopAudio();

    const waveElement = document.querySelector("#wave");

    if (waveElement) {
        waveElement.classList.add("hidden");
    }


    setStatus(
        "Ready"
    );

    setOrbState("idle");
}


// ============================================================
// TEST KOKORO VOICE
// ============================================================

async function testPriyaVoice() {

    const testMessage =
        "Hello, I'm Priya. How can I help you?";


    if (answerElement) {

        answerElement.textContent =
            testMessage;
    }


    if (questionDisplay) {

        questionDisplay.textContent =
            "Kokoro voice test";
    }


    if (categoryDisplay) {

        categoryDisplay.textContent =
            "";
    }


    await speak(
        testMessage
    );
}


// ============================================================
// BUTTONS
// ============================================================

const startButton =
    document.querySelector(
        "#start-priya"
    );


const stopButton =
    document.querySelector(
        "#stop-priya"
    );


const testVoiceButton =
    document.querySelector(
        "#test-voice"
    );


if (startButton) {

    startButton.addEventListener(
        "click",
        startPriya
    );
}


if (stopButton) {

    stopButton.addEventListener(
        "click",
        stopPriya
    );
}


if (testVoiceButton) {

    testVoiceButton.addEventListener(
        "click",
        testPriyaVoice
    );
}


if (clearChatButton) {

    clearChatButton.addEventListener(
        "click",
        () => {

            if (activeAskController) {
                activeAskController.abort();
                activeAskController = null;
            }

            stopAudio();

            chatContainer?.querySelectorAll(".message").forEach((message) => {
                message.remove();
            });

            // Keep the visible chat and the backend's temporary context in sync.
            fetch("/memory/clear", { method: "POST" }).catch(() => {
                // Clearing the UI should still work if the backend is unavailable.
            });

            uiThinking(false);
            setStatus("Ready");
            setOrbState("idle");
            shouldFollowChat = true;
            updateJumpToLatestControl();

        }
    );
}


// ============================================================
// TYPED QUESTION FORM
// ============================================================
//
// IMPORTANT:
// This is intentionally handled here.
// Do not add another submit listener for the
// same form in app.js, otherwise the question can
// be sent twice.
// ============================================================

const questionForm =
    document.querySelector(
        "#question-form"
    );


if (questionForm) {

    questionForm.addEventListener(
        "submit",
        async (event) => {

            event.preventDefault();


            const question =
                questionInput?.value?.trim() ||
                "";


            if (!question && !selectedImage) {
                return;
            }


            await askPriya(
                question
            );
        }
    );
}


// ============================================================
// EXPOSE FUNCTIONS FOR DEBUGGING
// ============================================================
//
// You can test these from Chrome DevTools:
//
// startPriya()
// stopPriya()
// testPriyaVoice()
// askPriya("What is the latest AI news?")
// ============================================================

window.startPriya =
    startPriya;

window.stopPriya =
    stopPriya;

window.testPriyaVoice =
    testPriyaVoice;

window.askPriya =
    askPriya;

window.speakPriya =
    speak;


// ============================================================
// LATEST HEADLINES LIST
// (Plain RSS display — separate from Priya's voice answers.)
// ============================================================

function renderSkeletons(container, count = 6) {

    container.innerHTML = Array.from({ length: count }).map(() => `
        <div class="skeleton-card">
            <div class="skeleton-line w40"></div>
            <div class="skeleton-line w90"></div>
            <div class="skeleton-line w60"></div>
        </div>
    `).join("");
}


async function loadHeadlines() {

    if (!headlinesElement) {
        return;
    }

    renderSkeletons(headlinesElement, 6);

    try {

        const response =
            await fetch("/news");

        const data =
            await response.json();

        if (!response.ok) {

            throw new Error(
                data.detail ||
                "Could not load headlines."
            );
        }

        const articles =
            data.articles || [];

        if (!articles.length) {

            headlinesElement.innerHTML =
                '<p class="empty">No headlines available right now.</p>';

            return;
        }

        headlinesElement.innerHTML = articles.map((article) => `
            <article class="headline">
                <span class="badge">${escapeHtml(article.category || "News")}</span>
                <h3>
                    <a href="${escapeHtml(article.url)}" target="_blank" rel="noreferrer">
                        ${escapeHtml(article.title)}
                    </a>
                </h3>
                <p>${escapeHtml(article.summary)}</p>
                <p class="meta">
                    <span>${escapeHtml(article.source)}</span>
                    <span>${escapeHtml(article.published_at)}</span>
                </p>
            </article>
        `).join("");

    } catch (error) {

        console.error(
            "Could not load headlines:",
            error
        );

        headlinesElement.innerHTML =
            `<p class="empty">${escapeHtml(error.message)}</p>`;
    }
}


if (refreshButton) {

    refreshButton.addEventListener(
        "click",
        loadHeadlines
    );
}


// Load headlines once on page open.
loadHeadlines();


// ============================================================
// MARKET DASHBOARD
// Rendered from real headlines only (backend never invents
// prices/trend numbers) — the sparkline bar is purely
// decorative, not a plotted value.
// ============================================================

async function loadMarket() {

    if (!marketElement) {
        return;
    }

    renderSkeletons(marketElement, 4);

    try {

        const response =
            await fetch("/market/news");

        const data =
            await response.json();

        if (!response.ok) {

            throw new Error(
                data.detail ||
                "Could not load market news."
            );
        }

        const articles =
            data.articles || [];

        if (!articles.length) {

            marketElement.innerHTML =
                '<p class="market-placeholder">No market updates available right now.</p>';

            return;
        }

        marketElement.innerHTML = articles.map((article) => `
            <div class="market-item">

                <div class="m-head">
                    <span class="m-name">${escapeHtml(article.source || "Market")}</span>
                    <span class="m-trend flat" title="Live headline, not a price feed">Live</span>
                </div>

                <p class="m-headline">${escapeHtml(article.title)}</p>

                <div class="sparkline"></div>

                <div class="m-meta">${escapeHtml(article.published_at || "")}</div>

            </div>
        `).join("");

    } catch (error) {

        console.error(
            "Could not load market news:",
            error
        );

        marketElement.innerHTML =
            `<p class="market-placeholder">${escapeHtml(error.message)}</p>`;
    }
}


if (refreshMarketButton) {

    refreshMarketButton.addEventListener(
        "click",
        loadMarket
    );
}


// Load market data once on page open.
loadMarket();
