const state = {
  user: null,
  authStep: "email",
  pendingEmail: "",
  selectedTag: "",
  query: "",
  questions: [],
  selectedQuestionId: null,
};

const els = {
  loggedOutView: document.querySelector("#loggedOutView"),
  loggedInView: document.querySelector("#loggedInView"),
  authForm: document.querySelector("#authForm"),
  authSubmit: document.querySelector("#authSubmit"),
  authMessage: document.querySelector("#authMessage"),
  emailInput: document.querySelector("#emailInput"),
  codeField: document.querySelector("#codeField"),
  codeInput: document.querySelector("#codeInput"),
  changeEmailButton: document.querySelector("#changeEmailButton"),
  currentUserName: document.querySelector("#currentUserName"),
  currentUserEmail: document.querySelector("#currentUserEmail"),
  logoutButton: document.querySelector("#logoutButton"),
  searchInput: document.querySelector("#searchInput"),
  tagList: document.querySelector("#tagList"),
  clearTagButton: document.querySelector("#clearTagButton"),
  activeFilterLabel: document.querySelector("#activeFilterLabel"),
  questionCount: document.querySelector("#questionCount"),
  questionList: document.querySelector("#questionList"),
  newQuestionButton: document.querySelector("#newQuestionButton"),
  questionComposer: document.querySelector("#questionComposer"),
  closeComposerButton: document.querySelector("#closeComposerButton"),
  questionForm: document.querySelector("#questionForm"),
  questionMessage: document.querySelector("#questionMessage"),
  publishQuestionButton: document.querySelector("#publishQuestionButton"),
  emptyDetail: document.querySelector("#emptyDetail"),
  questionDetail: document.querySelector("#questionDetail"),
  detailTags: document.querySelector("#detailTags"),
  detailTitle: document.querySelector("#detailTitle"),
  detailMeta: document.querySelector("#detailMeta"),
  detailDescription: document.querySelector("#detailDescription"),
  detailFiles: document.querySelector("#detailFiles"),
  commentList: document.querySelector("#commentList"),
  commentForm: document.querySelector("#commentForm"),
  commentBody: document.querySelector("#commentBody"),
  commentFiles: document.querySelector("#commentFiles"),
  commentSubmitButton: document.querySelector("#commentSubmitButton"),
  commentMessage: document.querySelector("#commentMessage"),
};

function setMessage(element, text, type = "") {
  element.textContent = text;
  element.className = `message ${type}`.trim();
}

function formatDate(value) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function fileLabel(file) {
  const type = file.mimeType || "";
  if (type.includes("pdf")) return "PDF";
  if (type.includes("image")) return "Image";
  return "File";
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed.");
  }
  return data;
}

function updateAuthUi() {
  const loggedIn = Boolean(state.user);
  els.loggedOutView.hidden = loggedIn;
  els.loggedInView.hidden = !loggedIn;
  els.currentUserName.textContent = state.user?.full_name || "";
  els.currentUserEmail.textContent = state.user?.email || "";
  els.newQuestionButton.disabled = !loggedIn;
  els.commentSubmitButton.disabled = !loggedIn;
  if (!loggedIn) {
    els.newQuestionButton.textContent = "Log In to Ask";
    els.commentSubmitButton.textContent = "Log In to Comment";
  } else {
    els.newQuestionButton.textContent = "New Question";
    els.commentSubmitButton.textContent = "Post Comment";
  }
}

function setAuthStep(step, email = "") {
  state.authStep = step;
  state.pendingEmail = email;
  const enteringCode = step === "code";
  els.codeField.hidden = !enteringCode;
  els.changeEmailButton.hidden = !enteringCode;
  els.emailInput.disabled = enteringCode;
  els.emailInput.value = email || els.emailInput.value;
  els.codeInput.required = enteringCode;
  els.authSubmit.textContent = enteringCode ? "Verify Code" : "Send Login Code";
  setMessage(els.authMessage, "");
  if (enteringCode) {
    els.codeInput.focus();
  } else {
    els.codeInput.value = "";
    els.emailInput.disabled = false;
    els.emailInput.focus();
  }
}

async function submitAuth(event) {
  event.preventDefault();
  setMessage(els.authMessage, "");
  els.authSubmit.disabled = true;
  try {
    if (state.authStep === "email") {
      const data = await requestJson("/api/auth/request-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: els.emailInput.value,
        }),
      });
      setAuthStep("code", data.email);
      setMessage(els.authMessage, "A 6-digit login code was sent to your school email.", "success");
      return;
    }

    const data = await requestJson("/api/auth/verify-code", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: state.pendingEmail,
        code: els.codeInput.value,
      }),
    });
    state.user = data.user;
    els.authForm.reset();
    setAuthStep("email");
    updateAuthUi();
    setMessage(els.authMessage, "Logged in.", "success");
  } catch (error) {
    setMessage(els.authMessage, error.message, "error");
  } finally {
    els.authSubmit.disabled = false;
  }
}

async function logout() {
  await requestJson("/api/logout", { method: "POST" });
  state.user = null;
  setAuthStep("email");
  updateAuthUi();
  setMessage(els.authMessage, "Logged out.", "success");
}

function renderTags() {
  for (const button of els.tagList.querySelectorAll(".tag-pill")) {
    button.classList.toggle("active", button.dataset.tag === state.selectedTag);
  }
  els.activeFilterLabel.textContent = state.selectedTag ? `Tag: ${state.selectedTag}` : "All tags";
}

function renderFileLinks(files) {
  if (!files.length) return "";
  return files
    .map(
      (file) => `
        <a class="file-link" href="${file.url}" target="_blank" rel="noreferrer">
          ${fileLabel(file)} · ${escapeHtml(file.originalName)}
        </a>
      `,
    )
    .join("");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderQuestions() {
  els.questionCount.textContent = state.questions.length;
  renderTags();

  if (!state.questions.length) {
    els.questionList.innerHTML = '<div class="empty-list">No questions match this search.</div>';
    return;
  }

  els.questionList.innerHTML = state.questions
    .map(
      (question) => `
        <button class="question-card ${question.id === state.selectedQuestionId ? "active" : ""}" type="button" data-question-id="${question.id}">
          <div class="inline-tags">
            ${question.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}
          </div>
          <h4>${escapeHtml(question.title)}</h4>
          <p>${escapeHtml(question.description)}</p>
          <div class="question-footer">
            <span>${escapeHtml(question.author)}</span>
            <span>${formatDate(question.createdAt)}</span>
            <span>${question.commentCount} comments</span>
            <span>${question.attachments.length} files</span>
          </div>
        </button>
      `,
    )
    .join("");
}

async function loadQuestions() {
  const params = new URLSearchParams();
  if (state.selectedTag) params.set("tag", state.selectedTag);
  if (state.query) params.set("q", state.query);
  const data = await requestJson(`/api/questions?${params.toString()}`);
  state.questions = data.questions;
  if (
    state.selectedQuestionId &&
    !state.questions.some((question) => question.id === state.selectedQuestionId)
  ) {
    state.selectedQuestionId = null;
    showEmptyDetail();
  }
  renderQuestions();
}

function showEmptyDetail() {
  els.emptyDetail.hidden = false;
  els.questionDetail.hidden = true;
}

function renderQuestionDetail(question) {
  state.selectedQuestionId = question.id;
  els.emptyDetail.hidden = true;
  els.questionDetail.hidden = false;
  els.detailTags.innerHTML = question.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("");
  els.detailTitle.textContent = question.title;
  els.detailMeta.textContent = `${question.author} · ${formatDate(question.createdAt)}`;
  els.detailDescription.textContent = question.description;
  els.detailFiles.innerHTML = renderFileLinks(question.attachments);

  if (!question.comments.length) {
    els.commentList.innerHTML = '<div class="empty-list">No answers yet. Be the first to help.</div>';
  } else {
    els.commentList.innerHTML = question.comments
      .map(
        (comment) => `
          <article class="comment-card">
            <div class="comment-top">
              <div>
                <strong>${escapeHtml(comment.author)}</strong>
                <div class="meta-text">${formatDate(comment.createdAt)}</div>
              </div>
              <div class="vote-group">
                <button class="vote-button helpful ${comment.myVote === 1 ? "active" : ""}" type="button" data-comment-id="${comment.id}" data-vote="1">
                  Helpful ${comment.helpful}
                </button>
                <button class="vote-button unhelpful ${comment.myVote === -1 ? "active" : ""}" type="button" data-comment-id="${comment.id}" data-vote="-1">
                  Unhelpful ${comment.unhelpful}
                </button>
              </div>
            </div>
            <p class="body-text">${escapeHtml(comment.body)}</p>
            <div class="file-list">${renderFileLinks(comment.attachments)}</div>
          </article>
        `,
      )
      .join("");
  }
  renderQuestions();
}

async function openQuestion(questionId) {
  const data = await requestJson(`/api/questions/${questionId}`);
  renderQuestionDetail(data.question);
}

async function publishQuestion(event) {
  event.preventDefault();
  if (!state.user) {
    setMessage(els.questionMessage, "Please log in before publishing a question.", "error");
    return;
  }

  const formData = new FormData(els.questionForm);
  els.publishQuestionButton.disabled = true;
  setMessage(els.questionMessage, "Publishing...");
  try {
    const data = await requestJson("/api/questions", {
      method: "POST",
      body: formData,
    });
    els.questionForm.reset();
    els.questionComposer.hidden = true;
    setMessage(els.questionMessage, "");
    await loadQuestions();
    renderQuestionDetail(data.question);
  } catch (error) {
    setMessage(els.questionMessage, error.message, "error");
  } finally {
    els.publishQuestionButton.disabled = false;
  }
}

async function publishComment(event) {
  event.preventDefault();
  if (!state.user || !state.selectedQuestionId) {
    setMessage(els.commentMessage, "Please log in and select a question first.", "error");
    return;
  }
  const formData = new FormData(els.commentForm);
  els.commentSubmitButton.disabled = true;
  setMessage(els.commentMessage, "Posting...");
  try {
    const data = await requestJson(`/api/questions/${state.selectedQuestionId}/comments`, {
      method: "POST",
      body: formData,
    });
    els.commentForm.reset();
    setMessage(els.commentMessage, "Comment posted.", "success");
    renderQuestionDetail(data.question);
    await loadQuestions();
  } catch (error) {
    setMessage(els.commentMessage, error.message, "error");
  } finally {
    els.commentSubmitButton.disabled = false;
    updateAuthUi();
  }
}

async function vote(commentId, value) {
  if (!state.user) {
    setMessage(els.commentMessage, "Please log in before voting.", "error");
    return;
  }
  const data = await requestJson(`/api/comments/${commentId}/vote`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value }),
  });
  renderQuestionDetail(data.question);
}

function setupEvents() {
  els.authForm.addEventListener("submit", submitAuth);
  els.changeEmailButton.addEventListener("click", () => setAuthStep("email"));
  els.logoutButton.addEventListener("click", logout);

  els.newQuestionButton.addEventListener("click", () => {
    if (!state.user) {
      setMessage(els.authMessage, "Log in or register before posting.", "error");
      return;
    }
    els.questionComposer.hidden = !els.questionComposer.hidden;
  });

  els.closeComposerButton.addEventListener("click", () => {
    els.questionComposer.hidden = true;
  });

  els.searchInput.addEventListener("input", () => {
    state.query = els.searchInput.value.trim();
    loadQuestions().catch(console.error);
  });

  els.tagList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-tag]");
    if (!button) return;
    state.selectedTag = button.dataset.tag === state.selectedTag ? "" : button.dataset.tag;
    loadQuestions().catch(console.error);
  });

  els.clearTagButton.addEventListener("click", () => {
    state.selectedTag = "";
    loadQuestions().catch(console.error);
  });

  els.questionList.addEventListener("click", (event) => {
    const card = event.target.closest("[data-question-id]");
    if (!card) return;
    openQuestion(Number(card.dataset.questionId)).catch(console.error);
  });

  els.commentList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-comment-id][data-vote]");
    if (!button) return;
    vote(Number(button.dataset.commentId), Number(button.dataset.vote)).catch((error) => {
      setMessage(els.commentMessage, error.message, "error");
    });
  });

  els.questionForm.addEventListener("submit", publishQuestion);
  els.commentForm.addEventListener("submit", publishComment);
}

async function init() {
  setupEvents();
  setAuthStep("email");
  const data = await requestJson("/api/me");
  state.user = data.user;
  updateAuthUi();
  await loadQuestions();
}

init().catch((error) => {
  setMessage(els.authMessage, error.message, "error");
});
