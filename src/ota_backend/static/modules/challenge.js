// challenge.js
//
// Cloudflare Turnstile orchestration. The widget renders invisibly
// (interaction-only appearance) and executes on demand from the OTA
// and resolve flows. Tokens are short-lived and reset after each
// request so the next call gets a fresh challenge.

import { api as _api, clientError } from "./api.js";
import { challengeElementIds, state } from "./state.js";
import { t } from "./i18n.js";

export function resetChallenge(action) {
  state.challengeTokens[action] = "";
  const widget = state.challengeWidgets[action];
  if (window.turnstile && widget !== null && widget !== undefined) {
    window.turnstile.reset(widget);
  }
}

export function settleChallenge(action, token, error) {
  const waiter = state.challengeWaiters[action];
  state.challengeWaiters[action] = null;
  window.clearTimeout(waiter?.timer);
  if (!waiter) return;
  if (error) {
    waiter.reject(error);
    return;
  }
  waiter.resolve(token);
}

export function requestChallengeToken(action) {
  if (!state.publicSite) return Promise.resolve("");
  if (!window.turnstile) {
    return Promise.reject(clientError("CHALLENGE_UNAVAILABLE", t("challenge.loading")));
  }
  const widget = state.challengeWidgets[action];
  if (widget === null || widget === undefined) {
    return Promise.reject(clientError("CHALLENGE_UNAVAILABLE", t("challenge.notReady")));
  }
  if (state.challengeWaiters[action]) {
    state.challengeWaiters[action].reject(clientError("CHALLENGE_RESTARTED", t("challenge.restarted")));
  }
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      settleChallenge(action, "", clientError("CHALLENGE_TIMEOUT", t("challenge.timeout")));
    }, 120000);
    state.challengeWaiters[action] = { resolve, reject, timer };
    state.challengeTokens[action] = "";
    window.turnstile.reset(widget);
    window.turnstile.execute(widget);
  });
}

export function mountTurnstile() {
  if (!state.publicSite || !state.turnstileSiteKey || !window.turnstile) return;
  const actions = state.resolverEnabled ? ["ota", "resolve"] : ["ota"];
  actions.forEach((action) => {
    const elementId = challengeElementIds[action];
    if (!elementId) return;
    if (state.challengeWidgets[action] !== null && state.challengeWidgets[action] !== undefined) return;
    state.challengeWidgets[action] = window.turnstile.render(`#${elementId}`, {
      sitekey: state.turnstileSiteKey,
      action,
      execution: "execute",
      appearance: "interaction-only",
      theme: "dark",
      callback: (token) => {
        state.challengeTokens[action] = token;
        settleChallenge(action, token, null);
      },
      "expired-callback": () => {
        state.challengeTokens[action] = "";
      },
      "error-callback": () => {
        settleChallenge(action, "", clientError("CHALLENGE_FAILED", t("challenge.failed")));
      },
      "timeout-callback": () => {
        settleChallenge(action, "", clientError("CHALLENGE_TIMEOUT", t("challenge.timeout")));
      },
      "unsupported-callback": () => {
        settleChallenge(action, "", clientError("CHALLENGE_UNSUPPORTED", t("challenge.unsupported")));
      },
    });
  });
}

export async function activeHeaders(action) {
  if (!state.publicSite) return {};
  const token = await requestChallengeToken(action);
  return { "X-Turnstile-Token": token };
}

// Unused re-export of api() kept to make the dependency direction
// explicit; future refactors that move HTTP calls into challenge.js
// can drop the underscore.
export { _api };
