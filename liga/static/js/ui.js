const flashNode = document.querySelector("#liga-flashes");
if (flashNode && window.Notyf) {
  const notyf = new Notyf({
    duration: 4000,
    dismissible: true,
    ripple: false,
    position: { x: "center", y: "top" },
    types: [
      { type: "error", background: "#9f1239", dismissible: true },
      { type: "info", background: "#01a29a", dismissible: true },
    ],
  });
  JSON.parse(flashNode.textContent || "[]").forEach(([category, message]) => {
    notyf.open({ type: category === "error" ? "error" : "info", message });
  });
}

const otp = document.querySelectorAll(".otp input");
otp.forEach((input, index) => {
  input.addEventListener("input", () => {
    input.value = input.value.replace(/\D/g, "").slice(-1);
    if (input.value && otp[index + 1]) otp[index + 1].focus();
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Backspace" && !input.value && otp[index - 1]) {
      otp[index - 1].focus();
    }
  });
});

const lobby = document.querySelector("[data-lobby]");
if (lobby) {
  const guest = document.querySelector("#lobby-guest");
  const start = document.querySelector("#lobby-start");
  const wait = document.querySelector("#lobby-wait");
  window.setInterval(async () => {
    try {
      const response = await fetch(lobby.dataset.lobby);
      const data = await response.json();
      if (data.url) window.location.href = data.url;
      if (data.guest && guest && start && wait) {
        guest.hidden = false;
        guest.textContent = data.guest;
        wait.textContent = `${data.guest} entrou. A mesa só abre quando você der pronto.`;
        start.hidden = false;
      }
    } catch (_error) {
      /* a próxima tentativa cobre a queda */
    }
  }, 1500);
}

document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    const value = button.dataset.copy;
    try {
      await navigator.clipboard.writeText(value);
      button.textContent = "COPIADO";
    } catch (_error) {
      button.textContent = value;
    }
  });
});

const USERNAME = /^[A-Za-z0-9_]{3,20}$/;
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function fieldState(input, form) {
  const value = input.value;
  const trimmed = value.trim();
  const rule = input.dataset.rule;
  const optional = input.dataset.optional === "1";
  if (!trimmed && optional) return { state: "ok", text: "" };
  if (!trimmed) return { state: "empty", text: "Preencha este campo." };
  if (rule === "nome") {
    if (trimmed.length > 40) return { state: "bad", text: "O nome cabe em 40 caracteres." };
    return { state: "ok", text: "Nome certo." };
  }
  if (rule === "username") {
    if (!USERNAME.test(trimmed)) return { state: "bad", text: "Use 3 a 20 letras, números ou _." };
    if (input.dataset.live === "1" && input.dataset.free === "0") return { state: "bad", text: "Esse usuário já existe." };
    if (input.dataset.live === "1" && input.dataset.free !== "1") return { state: "wait", text: "Conferindo o usuário…" };
    return { state: "ok", text: "Usuário disponível." };
  }
  if (rule === "email") {
    if (!EMAIL.test(trimmed)) return { state: "bad", text: "Esse e-mail não parece válido." };
    if (input.dataset.live === "1" && input.dataset.free === "0") return { state: "bad", text: "Esse e-mail já está em uso." };
    if (input.dataset.live === "1" && input.dataset.free !== "1") return { state: "wait", text: "Conferindo o e-mail…" };
    return { state: "ok", text: "E-mail certo." };
  }
  if (rule === "password") {
    if (value.length < 6) return { state: "bad", text: "Pelo menos 6 caracteres." };
    return { state: "ok", text: "Senha no tamanho certo." };
  }
  if (rule === "match") {
    const other = form.querySelector(`[name="${input.dataset.match}"]`);
    if (!other || value !== other.value) return { state: "bad", text: "As senhas não coincidem." };
    return { state: "ok", text: "As senhas coincidem." };
  }
  if (rule === "codigo") {
    if (!/^[A-Za-z0-9]{6}$/.test(trimmed)) return { state: "bad", text: "O código da sala tem 6 caracteres." };
    return { state: "ok", text: "Código no formato certo." };
  }
  if (rule === "sugestao") {
    if (trimmed.length < 8) return { state: "bad", text: "Escreva pelo menos 8 caracteres." };
    if (trimmed.length > 400) return { state: "bad", text: "A sugestão cabe em 400 caracteres." };
    return { state: "ok", text: `${trimmed.length}/400` };
  }
  if (rule === "bio") {
    if (value.length > 140) return { state: "bad", text: "A bio cabe em 140 caracteres." };
    return { state: "ok", text: value.length ? `${value.length}/140` : "" };
  }
  return { state: "ok", text: "" };
}

function paintField(input, result, reveal) {
  const block = input.closest(".field-block");
  const field = input.closest(".field");
  const message = block ? block.querySelector(".field-msg") : null;
  if (!field) return;
  field.classList.remove("ok", "bad");
  if (message) {
    message.classList.remove("ok", "bad");
    message.textContent = "";
  }
  const show = reveal || result.state === "ok" || result.state === "wait";
  if (!show || result.state === "empty") return;
  if (result.state === "ok") {
    field.classList.add("ok");
    if (message && result.text) {
      message.classList.add("ok");
      message.textContent = result.text;
    }
  } else if (result.state === "bad") {
    field.classList.add("bad");
    if (message) {
      message.classList.add("bad");
      message.textContent = result.text;
    }
  } else if (message && result.text) {
    message.textContent = result.text;
  }
}

document.querySelectorAll("form[data-verify]").forEach((form) => {
  const button = form.querySelector('button[type="submit"]');
  const status = form.querySelector("[data-status]");
  const inputs = [...form.querySelectorAll("[data-rule]")];
  const digits = [...form.querySelectorAll(".otp input")];
  let timer = 0;

  function liveQuery() {
    const params = new URLSearchParams();
    inputs.forEach((input) => {
      if (input.dataset.live !== "1") return;
      if (input.dataset.rule !== "username" && input.dataset.rule !== "email") return;
      const verdict = fieldState(input, form);
      if (verdict.state === "bad" || verdict.state === "empty") return;
      params.set(input.name, input.value.trim());
    });
    return params;
  }

  async function checkFree() {
    if (!form.dataset.check) return;
    const params = liveQuery();
    if ([...params.keys()].length === 0) return;
    const stamp = params.toString();
    try {
      const response = await fetch(`${form.dataset.check}?${stamp}`);
      const data = await response.json();
      if (liveQuery().toString() !== stamp) return;
      inputs.forEach((input) => {
        if (input.dataset.live !== "1" || !(input.dataset.rule in data)) return;
        input.dataset.free = data[input.dataset.rule] ? "1" : "0";
      });
    } catch (_error) {
      inputs.forEach((input) => {
        if (input.dataset.live === "1") input.dataset.free = "";
      });
    }
    refresh(false);
  }

  function refresh(reveal) {
    if (digits.length) {
      const ready = digits.every((input) => /^\d$/.test(input.value));
      if (button) button.disabled = !ready;
      if (status) {
        status.textContent = ready ? "Código completo." : "Digite os 4 números do código.";
        status.classList.toggle("ok", ready);
      }
      return;
    }
    const results = inputs.map((input) => fieldState(input, form));
    inputs.forEach((input, index) => paintField(input, results[index], reveal || input.dataset.touched === "1"));
    const waiting = results.some((item) => item.state === "wait");
    const problem = results.find((item) => item.state === "bad" || item.state === "empty");
    const ready = results.every((item) => item.state === "ok");
    if (button) button.disabled = !ready;
    if (status) {
      if (ready) status.textContent = "Tudo certo. Pode continuar.";
      else if (waiting) status.textContent = "Conferindo se está livre…";
      else if (reveal && problem) status.textContent = problem.text;
      else status.textContent = status.dataset.idle || status.textContent;
      status.classList.toggle("ok", ready);
    }
  }

  inputs.forEach((input) => {
    input.addEventListener("input", () => {
      if (input.dataset.live === "1") input.dataset.free = "";
      refresh(false);
      window.clearTimeout(timer);
      timer = window.setTimeout(checkFree, 350);
    });
    input.addEventListener("blur", () => {
      input.dataset.touched = "1";
      refresh(true);
    });
  });
  digits.forEach((input) => input.addEventListener("input", () => refresh(false)));
  form.addEventListener("submit", (event) => {
    inputs.forEach((input) => {
      input.dataset.touched = "1";
    });
    refresh(true);
    if (button && button.disabled) event.preventDefault();
  });
  if (status && !status.dataset.idle) status.dataset.idle = status.textContent;
  refresh(false);
  checkFree();
});

document.querySelectorAll('input[name="theme"]').forEach((input) => {
  input.addEventListener("change", () => {
    document.body.dataset.theme = input.value;
  });
});
