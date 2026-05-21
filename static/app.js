const state = {
  user: null,
  authMode: "login",
  authStep: "details",
  pendingEmail: "",
  pendingFullName: "",
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
  loginTab: document.querySelector("#loginTab"),
  registerTab: document.querySelector("#registerTab"),
  identifierLabel: document.querySelector("#identifierLabel"),
  fullNameField: document.querySelector("#fullNameField"),
  fullNameInput: document.querySelector("#fullNameInput"),
  passwordField: document.querySelector("#passwordField"),
  passwordInput: document.querySelector("#passwordInput"),
  confirmPasswordField: document.querySelector("#confirmPasswordField"),
  confirmPasswordInput: document.querySelector("#confirmPasswordInput"),
  emailInput: document.querySelector("#emailInput"),
  codeField: document.querySelector("#codeField"),
  codeInput: document.querySelector("#codeInput"),
  changeEmailButton: document.querySelector("#changeEmailButton"),
  currentUserName: document.querySelector("#currentUserName"),
  currentUserEmail: document.querySelector("#currentUserEmail"),
  currentUserRole: document.querySelector("#currentUserRole"),
  moderationButton: document.querySelector("#moderationButton"),
  feedbackListButton: document.querySelector("#feedbackListButton"),
  feedbackButton: document.querySelector("#feedbackButton"),
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
  feedbackPanel: document.querySelector("#feedbackPanel"),
  closeFeedbackButton: document.querySelector("#closeFeedbackButton"),
  feedbackForm: document.querySelector("#feedbackForm"),
  feedbackBody: document.querySelector("#feedbackBody"),
  feedbackSubmitButton: document.querySelector("#feedbackSubmitButton"),
  feedbackMessage: document.querySelector("#feedbackMessage"),
  moderationPanel: document.querySelector("#moderationPanel"),
  closeModerationButton: document.querySelector("#closeModerationButton"),
  moderationSummary: document.querySelector("#moderationSummary"),
  moderationQuestions: document.querySelector("#moderationQuestions"),
  moderationComments: document.querySelector("#moderationComments"),
  moderationUsers: document.querySelector("#moderationUsers"),
  moderationMessage: document.querySelector("#moderationMessage"),
  feedbackListPanel: document.querySelector("#feedbackListPanel"),
  closeFeedbackListButton: document.querySelector("#closeFeedbackListButton"),
  feedbackList: document.querySelector("#feedbackList"),
  feedbackListMessage: document.querySelector("#feedbackListMessage"),
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
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    throw new Error(data?.error || `Server returned ${response.status}. Please try again after deployment finishes.`);
  }
  if (!data) {
    throw new Error("Server returned an unreadable response. Please try again.");
  }
  return data;
}

function updateAuthUi() {
  const loggedIn = Boolean(state.user);
  els.loggedOutView.hidden = loggedIn;
  els.loggedInView.hidden = !loggedIn;
  els.currentUserName.textContent = state.user?.full_name || "";
  els.currentUserEmail.textContent = state.user?.email || "";
  els.currentUserRole.textContent = state.user?.role ? state.user.role.toUpperCase() : "";
  els.moderationButton.hidden = !["teacher", "developer"].includes(state.user?.role);
  els.feedbackListButton.hidden = state.user?.role !== "developer";
  if (!loggedIn) {
    els.feedbackPanel.hidden = true;
    els.moderationPanel.hidden = true;
    els.feedbackListPanel.hidden = true;
  }
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

function setAuthMode(mode) {
  state.authMode = mode;
  state.pendingEmail = "";
  state.pendingFullName = "";
  state.authStep = "details";
  els.authForm.reset();
  setAuthStep("details");
}

function setAuthStep(step, email = "", fullName = "") {
  state.authStep = step;
  state.pendingEmail = email;
  state.pendingFullName = fullName;
  const enteringCode = step === "code";
  const registering = state.authMode === "register";
  els.loginTab.classList.toggle("active", !registering);
  els.registerTab.classList.toggle("active", registering);
  els.loginTab.disabled = enteringCode;
  els.registerTab.disabled = enteringCode;
  els.identifierLabel.textContent = registering ? "School Email" : "Email or Account Name";
  els.emailInput.type = registering ? "email" : "text";
  els.emailInput.placeholder = registering ? "name@stececile.ca" : "Email or First L";
  els.emailInput.autocomplete = registering ? "email" : "username";
  els.fullNameField.hidden = !registering;
  els.confirmPasswordField.hidden = !registering;
  els.fullNameInput.required = registering;
  els.confirmPasswordInput.required = registering;
  els.passwordInput.autocomplete = registering ? "new-password" : "current-password";
  els.fullNameInput.disabled = enteringCode;
  els.passwordInput.disabled = enteringCode;
  els.confirmPasswordInput.disabled = enteringCode;
  els.codeField.hidden = !enteringCode;
  els.changeEmailButton.hidden = !enteringCode;
  els.emailInput.disabled = enteringCode;
  els.emailInput.value = email || els.emailInput.value;
  els.fullNameInput.value = fullName || els.fullNameInput.value;
  els.codeInput.required = enteringCode;
  if (enteringCode) {
    els.authSubmit.textContent = registering ? "Create Account" : "Verify Code";
  } else {
    els.authSubmit.textContent = registering ? "Send Register Code" : "Send Login Code";
  }
  setMessage(els.authMessage, "");
  if (enteringCode) {
    els.codeInput.focus();
  } else {
    els.codeInput.value = "";
    els.fullNameInput.disabled = false;
    els.passwordInput.disabled = false;
    els.confirmPasswordInput.disabled = false;
    els.emailInput.disabled = false;
    els.emailInput.focus();
  }
}

async function submitAuth(event) {
  event.preventDefault();
  setMessage(els.authMessage, "");
  els.authSubmit.disabled = true;
  try {
    if (state.authStep === "details") {
      if (state.authMode === "register" && els.passwordInput.value !== els.confirmPasswordInput.value) {
        throw new Error("Passwords do not match.");
      }
      const endpoint = state.authMode === "register" ? "/api/auth/register/request-code" : "/api/auth/login/start";
      const body = state.authMode === "register"
        ? {
            email: els.emailInput.value,
            fullName: els.fullNameInput.value,
            password: els.passwordInput.value,
          }
        : {
            identifier: els.emailInput.value,
            password: els.passwordInput.value,
          };
      const data = await requestJson(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setAuthStep("code", data.email, els.fullNameInput.value);
      setMessage(els.authMessage, "A 6-digit code was sent to your school email.", "success");
      return;
    }

    const endpoint = state.authMode === "register" ? "/api/auth/register/verify" : "/api/auth/login/verify";
    const body = state.authMode === "register"
      ? {
          email: state.pendingEmail,
          fullName: state.pendingFullName,
          password: els.passwordInput.value,
          code: els.codeInput.value,
        }
      : {
          email: state.pendingEmail,
          code: els.codeInput.value,
        };
    const data = await requestJson(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    state.user = data.user;
    els.authForm.reset();
    setAuthMode("login");
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
  setAuthMode("login");
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

function roleLabel(role) {
  if (role === "developer") return "Developer";
  if (role === "teacher") return "Teacher";
  return "Student";
}

async function submitFeedback(event) {
  event.preventDefault();
  if (!state.user) {
    setMessage(els.feedbackMessage, "Please log in before sending feedback.", "error");
    return;
  }
  els.feedbackSubmitButton.disabled = true;
  setMessage(els.feedbackMessage, "Sending...");
  try {
    await requestJson("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: els.feedbackBody.value }),
    });
    els.feedbackForm.reset();
    setMessage(els.feedbackMessage, "Feedback sent.", "success");
  } catch (error) {
    setMessage(els.feedbackMessage, error.message, "error");
  } finally {
    els.feedbackSubmitButton.disabled = false;
  }
}

async function loadModeration() {
  setMessage(els.moderationMessage, "Loading...");
  const data = await requestJson("/api/moderation/overview");
  els.moderationSummary.innerHTML = `
    <span>${data.users.length} users</span>
    <span>${data.questions.length} recent questions</span>
    <span>${data.comments.length} recent comments</span>
  `;
  els.moderationQuestions.innerHTML = data.questions.length
    ? data.questions
        .map(
          (question) => `
            <article class="moderation-item">
              <div>
                <strong>${escapeHtml(question.title)}</strong>
                <p>${escapeHtml(question.description)}</p>
                <span>${escapeHtml(question.author)} · ${escapeHtml(question.author_email || "")} · ${formatDate(question.created_at)}</span>
              </div>
              <button class="danger-button compact-danger" type="button" data-delete-question="${question.id}">Delete</button>
            </article>
          `,
        )
        .join("")
    : '<div class="empty-list">No questions yet.</div>';
  els.moderationComments.innerHTML = data.comments.length
    ? data.comments
        .map(
          (comment) => `
            <article class="moderation-item">
              <div>
                <strong>${escapeHtml(comment.question_title)}</strong>
                <p>${escapeHtml(comment.body)}</p>
                <span>${escapeHtml(comment.author)} · ${escapeHtml(comment.author_email || "")} · ${formatDate(comment.created_at)}</span>
              </div>
              <button class="danger-button compact-danger" type="button" data-delete-comment="${comment.id}">Delete</button>
            </article>
          `,
        )
        .join("")
    : '<div class="empty-list">No comments yet.</div>';
  els.moderationUsers.innerHTML = data.users.length
    ? data.users
        .map(
          (user) => `
            <article class="moderation-item">
              <div>
                <strong>${escapeHtml(user.full_name)}</strong>
                <p>${escapeHtml(user.email || "No email")} · ${roleLabel(user.role)}</p>
                <span>${user.question_count} questions · ${user.comment_count} comments · joined ${formatDate(user.created_at)}</span>
              </div>
            </article>
          `,
        )
        .join("")
    : '<div class="empty-list">No users yet.</div>';
  setMessage(els.moderationMessage, "");
}

async function deleteModerationItem(kind, id) {
  const endpoint =
    kind === "question"
      ? `/api/moderation/questions/${id}`
      : `/api/moderation/comments/${id}`;
  await requestJson(endpoint, { method: "DELETE" });
  await loadModeration();
  await loadQuestions();
  if (kind === "question" && state.selectedQuestionId === id) {
    state.selectedQuestionId = null;
    showEmptyDetail();
  } else if (state.selectedQuestionId) {
    openQuestion(state.selectedQuestionId).catch(() => showEmptyDetail());
  }
}

async function loadFeedbackList() {
  setMessage(els.feedbackListMessage, "Loading...");
  const data = await requestJson("/api/feedback");
  els.feedbackList.innerHTML = data.feedback.length
    ? data.feedback
        .map(
          (item) => `
            <article class="moderation-item">
              <div>
                <strong>${escapeHtml(item.author)} · ${roleLabel(item.author_role)}</strong>
                <p>${escapeHtml(item.body)}</p>
                <span>${escapeHtml(item.author_email || "")} · ${formatDate(item.created_at)}</span>
              </div>
            </article>
          `,
        )
        .join("")
    : '<div class="empty-list">No feedback yet.</div>';
  setMessage(els.feedbackListMessage, "");
}

function setupEvents() {
  els.authForm.addEventListener("submit", submitAuth);
  els.loginTab.addEventListener("click", () => setAuthMode("login"));
  els.registerTab.addEventListener("click", () => setAuthMode("register"));
  els.changeEmailButton.addEventListener("click", () => setAuthStep("details"));
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

  els.feedbackButton.addEventListener("click", () => {
    els.feedbackPanel.hidden = !els.feedbackPanel.hidden;
  });

  els.closeFeedbackButton.addEventListener("click", () => {
    els.feedbackPanel.hidden = true;
  });

  els.moderationButton.addEventListener("click", () => {
    els.moderationPanel.hidden = !els.moderationPanel.hidden;
    if (!els.moderationPanel.hidden) {
      loadModeration().catch((error) => setMessage(els.moderationMessage, error.message, "error"));
    }
  });

  els.closeModerationButton.addEventListener("click", () => {
    els.moderationPanel.hidden = true;
  });

  els.feedbackListButton.addEventListener("click", () => {
    els.feedbackListPanel.hidden = !els.feedbackListPanel.hidden;
    if (!els.feedbackListPanel.hidden) {
      loadFeedbackList().catch((error) => setMessage(els.feedbackListMessage, error.message, "error"));
    }
  });

  els.closeFeedbackListButton.addEventListener("click", () => {
    els.feedbackListPanel.hidden = true;
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
  els.feedbackForm.addEventListener("submit", submitFeedback);

  els.moderationPanel.addEventListener("click", (event) => {
    const questionButton = event.target.closest("[data-delete-question]");
    const commentButton = event.target.closest("[data-delete-comment]");
    if (questionButton) {
      deleteModerationItem("question", Number(questionButton.dataset.deleteQuestion)).catch((error) => {
        setMessage(els.moderationMessage, error.message, "error");
      });
    }
    if (commentButton) {
      deleteModerationItem("comment", Number(commentButton.dataset.deleteComment)).catch((error) => {
        setMessage(els.moderationMessage, error.message, "error");
      });
    }
  });
}

async function init() {
  setupEvents();
  setAuthMode("login");
  const data = await requestJson("/api/me");
  state.user = data.user;
  updateAuthUi();
  await loadQuestions();
}

init().catch((error) => {
  setMessage(els.authMessage, error.message, "error");
});
