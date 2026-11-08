"use strict";

const ERROR_MESSAGES = {
  409: "Nothing indexed yet: upload a PDF first.",
  429: "Gemini quota reached. Wait a minute and try again.",
  503: "Server has no GEMINI_API_KEY. Add it to .env and restart the server.",
};

const documentsList = document.getElementById("documents-list");
const documentsStatus = document.getElementById("documents-status");
const uploadStatus = document.getElementById("upload-status");
const askStatus = document.getElementById("ask-status");
const fileInput = document.getElementById("file-input");
const questionInput = document.getElementById("question-input");
const answerBox = document.getElementById("answer");
const answerText = document.getElementById("answer-text");
const sourcesHeading = document.getElementById("sources-heading");
const sourcesList = document.getElementById("sources-list");

/** Friendly text for a failed response. Known statuses win over the server's detail. */
function errorMessage(status, body) {
  if (ERROR_MESSAGES[status]) {
    return ERROR_MESSAGES[status];
  }
  const detail = body && body.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (status === 422) {
    return "Invalid request";
  }
  return `Request failed (HTTP ${status})`;
}

/** fetch + JSON. Throws an Error whose message is safe to show to the user. */
async function api(path, options) {
  let response;
  try {
    response = await fetch(path, options);
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error("Cannot reach the server. Is uvicorn running?");
    }
    throw error;
  }

  let body = null;
  try {
    body = await response.json();
  } catch {
    // Non-JSON body (e.g. a proxy error page): fall back to the status message.
  }
  if (!response.ok) {
    throw new Error(errorMessage(response.status, body));
  }
  return body;
}

/** Disable a button and swap its label while a request runs. */
function setBusy(button, busy, busyLabel) {
  if (busy) {
    button.dataset.label = button.textContent;
    button.textContent = busyLabel;
  } else if (button.dataset.label) {
    button.textContent = button.dataset.label;
  }
  button.disabled = busy;
}

function showStatus(element, text, isError = false) {
  element.textContent = text;
  element.classList.toggle("error", isError);
}

function renderDocuments(docs) {
  documentsList.replaceChildren();
  if (docs.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No documents yet.";
    documentsList.append(item);
    return;
  }
  for (const doc of docs) {
    const item = document.createElement("li");
    const count = document.createElement("span");
    count.className = "count";
    count.textContent = `${doc.chunks} chunks`;
    item.append(doc.document, count);
    documentsList.append(item);
  }
}

async function loadDocuments() {
  try {
    renderDocuments(await api("/documents"));
    showStatus(documentsStatus, "");
  } catch (error) {
    showStatus(documentsStatus, error.message, true);
  }
}

async function uploadPdf(event) {
  event.preventDefault();
  const button = document.getElementById("upload-button");
  const file = fileInput.files[0];
  if (!file) {
    return;
  }
  const form = new FormData();
  form.append("file", file); // the browser sets the multipart Content-Type (with boundary)

  setBusy(button, true, "Indexing...");
  showStatus(uploadStatus, "");
  try {
    const result = await api("/documents", { method: "POST", body: form });
    const message =
      result.status === "unchanged"
        ? `${result.document} was already indexed (no changes, ${result.chunks} chunks).`
        : `Indexed ${result.document} (${result.chunks} chunks).`;
    showStatus(uploadStatus, message);
    fileInput.value = "";
    await loadDocuments();
  } catch (error) {
    showStatus(uploadStatus, error.message, true);
  } finally {
    setBusy(button, false);
  }
}

function clearAnswer() {
  answerBox.hidden = true;
  answerText.textContent = "";
  answerText.classList.remove("not-found");
  sourcesHeading.hidden = false;
  sourcesList.hidden = false;
  sourcesList.replaceChildren();
}

function renderAnswer(result) {
  clearAnswer();
  answerText.textContent = result.answer;

  if (!result.found) {
    answerText.classList.add("not-found");
    sourcesHeading.hidden = true;
    sourcesList.hidden = true;
  } else {
    sourcesHeading.textContent = result.sources_cited
      ? "Sources"
      : "Retrieved excerpts (the model cited none)";
    for (const source of result.sources) {
      const item = document.createElement("li");
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.textContent = `[${source.number}]`;
      item.append(badge, `${source.document}, p. ${source.page}`);
      sourcesList.append(item);
    }
  }
  answerBox.hidden = false;
}

async function askQuestion(event) {
  event.preventDefault();
  const button = document.getElementById("ask-button");
  const question = questionInput.value.trim();
  if (!question) {
    return;
  }

  questionInput.value = ""; // ready for the next question while this one is answered
  setBusy(button, true, "Thinking...");
  showStatus(askStatus, "");
  clearAnswer();
  try {
    const result = await api("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    renderAnswer(result);
  } catch (error) {
    showStatus(askStatus, error.message, true);
  } finally {
    setBusy(button, false);
  }
}

document.getElementById("refresh-button").addEventListener("click", loadDocuments);
document.getElementById("upload-form").addEventListener("submit", uploadPdf);
document.getElementById("ask-form").addEventListener("submit", askQuestion);
loadDocuments();
