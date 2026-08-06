const state = {
  queue: [],
  selectedId: null,
  detail: null,
  dryRun: true,
  busy: false,
};

const elements = {
  queueList: document.querySelector("#queue-list"),
  queueCount: document.querySelector("#queue-count"),
  transcriptHeading: document.querySelector("#transcript-heading"),
  conversationMeta: document.querySelector("#conversation-meta"),
  customerDetails: document.querySelector("#customer-details"),
  languageBadge: document.querySelector("#language-badge"),
  transcript: document.querySelector("#transcript"),
  editor: document.querySelector("#draft-editor"),
  confidenceBadge: document.querySelector("#confidence-badge"),
  internalNote: document.querySelector("#internal-note"),
  actionStatus: document.querySelector("#action-status"),
  dryRunBadge: document.querySelector("#dry-run-badge"),
  syncButton: document.querySelector("#sync-button"),
  approveButton: document.querySelector("#approve-button"),
  saveButton: document.querySelector("#save-button"),
  rejectButton: document.querySelector("#reject-button"),
  skipButton: document.querySelector("#skip-button"),
  regenerateButton: document.querySelector("#regenerate-button"),
};

const draftActionButtons = [
  elements.approveButton,
  elements.saveButton,
  elements.rejectButton,
  elements.skipButton,
  elements.regenerateButton,
];

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      message = payload.detail || message;
    } catch {
      // Keep the HTTP status message when the response is not JSON.
    }
    throw new Error(message);
  }

  return response.json();
}

function setStatus(message = "", isError = false) {
  elements.actionStatus.textContent = message;
  elements.actionStatus.classList.toggle("error", isError);
}

function setBusy(busy, message = "") {
  state.busy = busy;
  elements.syncButton.disabled = busy;
  const hasDraft = Boolean(state.selectedId);
  draftActionButtons.forEach((button) => {
    button.disabled = busy || !hasDraft;
  });
  elements.editor.disabled = busy || !hasDraft;
  if (message) setStatus(message);
}

function formatConfidence(value) {
  const confidence = Number(value);
  if (!Number.isFinite(confidence)) return null;
  return confidence <= 1
    ? `${Math.round(confidence * 100)}% confidence`
    : `${Math.round(confidence)}% confidence`;
}

function queueLabel(item) {
  return item.customer_name || item.customer_email || "Unknown customer";
}

function renderQueue() {
  elements.queueCount.textContent = String(state.queue.length);
  elements.queueList.replaceChildren();

  if (!state.queue.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No drafts need review. Sync to check for new conversations.";
    elements.queueList.append(empty);
    return;
  }

  state.queue.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "queue-item";
    button.classList.toggle("selected", item.id === state.selectedId);
    button.setAttribute("aria-pressed", String(item.id === state.selectedId));

    const subject = document.createElement("span");
    subject.className = "queue-subject";
    subject.textContent = item.subject || "No subject";

    const customer = document.createElement("span");
    customer.className = "queue-customer";
    customer.textContent = queueLabel(item);

    const preview = document.createElement("span");
    preview.className = "queue-preview";
    preview.textContent = item.edited_text || item.draft_text || "Empty draft";

    button.append(subject, customer, preview);
    button.addEventListener("click", () => selectDraft(item.id));
    elements.queueList.append(button);
  });
}

function transcriptMessages(transcript) {
  if (Array.isArray(transcript)) {
    return transcript.map((message) => {
      if (typeof message === "string") return { role: "Message", text: message };
      const role =
        message.role ||
        message.sender_type ||
        message.actor_type ||
        (message.direction === "inbound" ? "Customer" : "Agent");
      const text =
        message.body ||
        message.text ||
        message.message ||
        message.content?.text ||
        message.content?.body ||
        "";
      return { role: String(role), text: String(text) };
    });
  }

  return String(transcript || "")
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => {
      const match = line.match(/^(Customer|Agent):\s*(.*)$/i);
      return match
        ? { role: match[1], text: match[2] }
        : { role: "Message", text: line };
    });
}

function renderTranscript(transcript) {
  elements.transcript.replaceChildren();
  const messages = transcriptMessages(transcript);

  if (!messages.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No transcript is available for this conversation.";
    elements.transcript.append(empty);
    return;
  }

  messages.forEach((message) => {
    const article = document.createElement("article");
    const isAgent = /agent|support|admin/i.test(message.role);
    article.className = `message${isAgent ? " agent" : ""}`;

    const role = document.createElement("span");
    role.className = "message-role";
    role.textContent = message.role;

    const body = document.createElement("span");
    body.textContent = message.text;

    article.append(role, body);
    elements.transcript.append(article);
  });
}

function clearDetail() {
  state.selectedId = null;
  state.detail = null;
  elements.transcriptHeading.textContent = "Select a draft";
  elements.conversationMeta.textContent = "Conversation";
  elements.customerDetails.hidden = true;
  elements.languageBadge.hidden = true;
  elements.confidenceBadge.hidden = true;
  elements.internalNote.hidden = true;
  elements.editor.value = "";
  elements.editor.placeholder = "Select a draft to begin editing";
  elements.transcript.innerHTML =
    '<p class="empty-state">Choose a draft from the queue to view its transcript.</p>';
  setBusy(false);
}

function renderDetail(detail) {
  state.detail = detail;
  elements.transcriptHeading.textContent = detail.subject || "No subject";
  elements.conversationMeta.textContent =
    detail.conversation_id ? `Conversation ${detail.conversation_id}` : "Conversation";

  const customer = [detail.customer_name, detail.customer_email].filter(Boolean).join(" · ");
  elements.customerDetails.textContent = customer || "Customer details unavailable";
  elements.customerDetails.hidden = false;

  elements.languageBadge.textContent = (detail.language || "unknown").toUpperCase();
  elements.languageBadge.hidden = false;

  const confidence = formatConfidence(detail.confidence);
  elements.confidenceBadge.textContent = confidence || "";
  elements.confidenceBadge.hidden = !confidence;

  elements.editor.value = detail.edited_text ?? detail.draft_text ?? "";
  elements.editor.placeholder = "Write a response";

  elements.internalNote.textContent = detail.internal_note
    ? `Internal note: ${detail.internal_note}`
    : "";
  elements.internalNote.hidden = !detail.internal_note;

  renderTranscript(detail.transcript);
  setBusy(false);
}

async function selectDraft(draftId) {
  state.selectedId = draftId;
  renderQueue();
  setBusy(true, "Loading draft…");

  try {
    const detail = await request(`/api/drafts/${encodeURIComponent(draftId)}`);
    if (state.selectedId !== draftId) return;
    renderDetail(detail);
    setStatus("");
  } catch (error) {
    setBusy(false);
    setStatus(error.message, true);
  }
}

async function loadQueue({ preserveSelection = false } = {}) {
  const previousId = preserveSelection ? state.selectedId : null;
  const queue = await request("/api/queue");
  state.queue = Array.isArray(queue) ? queue : [];

  if (previousId && state.queue.some((item) => item.id === previousId)) {
    state.selectedId = previousId;
  } else {
    clearDetail();
  }
  renderQueue();
}

async function runDraftAction(action, body, pendingMessage, successMessage) {
  if (!state.selectedId || state.busy) return;
  const draftId = state.selectedId;
  setBusy(true, pendingMessage);

  try {
    const result = await request(
      `/api/drafts/${encodeURIComponent(draftId)}/${action}`,
      { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) },
    );
    setStatus(typeof successMessage === "function" ? successMessage(result) : successMessage);
    return result;
  } catch (error) {
    setStatus(error.message, true);
    throw error;
  } finally {
    setBusy(false);
  }
}

elements.saveButton.addEventListener("click", async () => {
  try {
    await runDraftAction(
      "save",
      { text: elements.editor.value },
      "Saving draft…",
      "Draft saved.",
    );
    await loadQueue({ preserveSelection: true });
  } catch {
    // The action status already contains the API error.
  }
});

elements.approveButton.addEventListener("click", async () => {
  if (!state.dryRun) {
    const confirmed = window.confirm(
      "Live mode is active. Approve and send this response to the customer?",
    );
    if (!confirmed) return;
  }

  try {
    await runDraftAction(
      "approve",
      { text: elements.editor.value },
      state.dryRun ? "Simulating approval…" : "Sending response…",
      (result) =>
        result.status === "sent_simulated"
          ? "Approved in dry-run. Nothing was sent."
          : "Response sent.",
    );
    await loadQueue();
  } catch {
    // The action status already contains the API error.
  }
});

elements.rejectButton.addEventListener("click", async () => {
  const reason = window.prompt("Optional rejection reason:", "");
  if (reason === null) return;
  try {
    await runDraftAction("reject", { reason: reason || null }, "Rejecting draft…", "Draft rejected.");
    await loadQueue();
  } catch {
    // The action status already contains the API error.
  }
});

elements.skipButton.addEventListener("click", async () => {
  try {
    await runDraftAction("skip", undefined, "Skipping draft…", "Draft skipped.");
    await loadQueue();
  } catch {
    // The action status already contains the API error.
  }
});

elements.regenerateButton.addEventListener("click", async () => {
  const instruction = window.prompt("Optional instruction for the new draft:", "");
  if (instruction === null) return;
  try {
    const result = await runDraftAction(
      "regenerate",
      { instruction: instruction || null },
      "Regenerating draft…",
      "Draft regenerated.",
    );
    elements.editor.value = result.text || "";
    await loadQueue({ preserveSelection: true });
    await selectDraft(state.selectedId);
  } catch {
    // The action status already contains the API error.
  }
});

elements.syncButton.addEventListener("click", async () => {
  setBusy(true, "Syncing conversations…");
  try {
    const result = await request("/api/sync", { method: "POST" });
    await loadQueue({ preserveSelection: true });
    setStatus(
      `Sync complete: ${result.conversations_seen ?? 0} checked, ${result.drafts_created ?? 0} drafts added.`,
    );
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setBusy(false);
  }
});

async function initialize() {
  try {
    const status = await request("/api/status");
    state.dryRun = Boolean(status.dry_run);
    elements.dryRunBadge.textContent = state.dryRun ? "Dry-run mode" : "LIVE SEND";
    elements.dryRunBadge.classList.toggle("live", !state.dryRun);
  } catch (error) {
    elements.dryRunBadge.textContent = "Mode unavailable";
    setStatus(error.message, true);
  }

  try {
    await loadQueue();
  } catch (error) {
    state.queue = [];
    renderQueue();
    setStatus(error.message, true);
  }
}

initialize();
