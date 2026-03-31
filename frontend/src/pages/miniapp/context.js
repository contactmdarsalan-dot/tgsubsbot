import { createContext, useContext } from "react";

export const API = process.env.REACT_APP_BACKEND_URL + "/api";
export const tg = typeof window !== "undefined" ? window.Telegram?.WebApp : null;

export const MiniAppContext = createContext(null);
export const useMiniApp = () => useContext(MiniAppContext);

export function getTelegramUser() {
  if (tg?.initDataUnsafe?.user) return tg.initDataUnsafe.user;
  const params = new URLSearchParams(window.location.search);
  const testId = params.get("tg_id");
  if (testId) return { id: parseInt(testId), first_name: params.get("tg_name") || "Tester" };
  return null;
}

export function copyToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text).then(() => { if (tg) tg.showAlert("Copied: " + text); }).catch(() => fallbackCopy(text));
  } else { fallbackCopy(text); }
}

function fallbackCopy(text) {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.cssText = "position:fixed;top:-9999px;left:-9999px";
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  document.body.removeChild(ta);
  if (tg) tg.showAlert("Copied: " + text);
}
