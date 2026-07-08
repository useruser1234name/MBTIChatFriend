const mbtiEl = document.querySelector("#mbti");
const promptModeEl = document.querySelector("#promptMode");
const personaEl = document.querySelector("#persona");
const userRoleEl = document.querySelector("#userRole");
const situationEl = document.querySelector("#situation");
const formEl = document.querySelector("#form");
const messageEl = document.querySelector("#message");
const messagesEl = document.querySelector("#messages");
const statusEl = document.querySelector("#status");
const resetEl = document.querySelector("#reset");
const sendEl = document.querySelector("#send");

let history = [];

function addMessage(role, content) {
  const el = document.createElement("div");
  el.className = `message ${role}`;
  el.textContent = content;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function setBusy(isBusy) {
  sendEl.disabled = isBusy;
  messageEl.disabled = isBusy;
  statusEl.textContent = isBusy ? "응답 생성 중" : "대기 중";
}

resetEl.addEventListener("click", () => {
  history = [];
  messagesEl.innerHTML = "";
  statusEl.textContent = "대화가 초기화됨";
});

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = messageEl.value.trim();
  if (!message) return;

  addMessage("user", message);
  history.push({ role: "user", content: message });
  messageEl.value = "";
  setBusy(true);

  try {
    const response = await fetch("/api/v1/web-chat/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        mbti: mbtiEl.value,
        prompt_mode: promptModeEl.value,
        persona: personaEl.value,
        user_role: userRoleEl.value,
        situation: situationEl.value,
        history: history.slice(-12),
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "요청 실패");
    }

    addMessage("assistant", data.reply);
    history.push({ role: "assistant", content: data.reply });
    statusEl.textContent = data.mocked
      ? `목업 응답 · ${data.prompt_mode}`
      : `모델: ${data.model} · ${data.prompt_mode}`;
  } catch (error) {
    const text = error instanceof Error ? error.message : "알 수 없는 오류";
    addMessage("assistant", `오류: ${text}`);
    statusEl.textContent = "오류 발생";
  } finally {
    setBusy(false);
    messageEl.focus();
  }
});
