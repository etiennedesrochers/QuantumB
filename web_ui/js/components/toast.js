/** Toast notifications (replaces the legacy alert()/confirm() calls). */

import { el } from "../dom.js";

const HOST = () => document.getElementById("toasts");

function show(kind, message, timeout) {
  const toast = el("div", { class: `toast toast-${kind}`, role: "status" }, [
    el("span", { class: "toast-text", text: message }),
    el("button", { class: "toast-close", type: "button", "aria-label": "Dismiss" }, ["\u00d7"]),
  ]);
  toast.querySelector(".toast-close").addEventListener("click", () => toast.remove());
  HOST().append(toast);
  if (timeout) setTimeout(() => toast.remove(), timeout);
  return toast;
}

export const toast = {
  success: (message) => show("success", message, 4000),
  info: (message) => show("info", message, 4000),
  error: (message) => show("error", message, 9000),
};

/** Promise-based confirmation dialog; resolves to the chosen value. */
export function confirmDialog({ title, message, choices }) {
  return new Promise((resolve) => {
    const close = (value) => {
      backdrop.remove();
      resolve(value);
    };

    const buttons = choices.map((choice) =>
      el("button", {
        type: "button",
        class: `btn ${choice.variant || "btn-secondary"}`,
        onClick: () => close(choice.value),
      }, [choice.label])
    );

    const backdrop = el("div", { class: "modal-backdrop" }, [
      el("div", { class: "modal", role: "dialog", "aria-modal": "true" }, [
        el("h3", { class: "modal-title", text: title }),
        el("p", { class: "modal-body", text: message }),
        el("div", { class: "modal-actions" }, buttons),
      ]),
    ]);

    backdrop.addEventListener("click", (event) => {
      if (event.target === backdrop) close(null);
    });
    document.body.append(backdrop);
    buttons[buttons.length - 1]?.focus();
  });
}

export function confirmAction(message, { confirmLabel = "Confirm", title = "Are you sure?" } = {}) {
  return confirmDialog({
    title,
    message,
    choices: [
      { label: "Cancel", value: false },
      { label: confirmLabel, value: true, variant: "btn-danger" },
    ],
  }).then(Boolean);
}
