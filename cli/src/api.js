import { getServer } from "./config.js";

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

/**
 * 调用 gesellschaft API。
 * @param {string} method HTTP 方法
 * @param {string} p 路径(以 / 开头)
 * @param {{token?: string, json?: object, form?: FormData, raw?: boolean}} opts
 * @returns {Promise<any>} raw=true 返回 Response
 */
export async function api(method, p, opts = {}) {
  const url = getServer() + p;
  const headers = {};
  if (opts.token) headers.Authorization = "Bearer " + opts.token;
  let body;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    body = opts.form;
  }
  const resp = await fetch(url, { method, headers, body });
  if (opts.raw) return resp;
  const text = await resp.text();
  let data = null;
  try {
    data = JSON.parse(text);
  } catch {
    data = text;
  }
  if (!resp.ok) {
    const detail =
      typeof data === "object" && data && data.detail ? data.detail : text.slice(0, 200);
    throw new ApiError(resp.status, `HTTP ${resp.status}: ${detail}`);
  }
  return data;
}

/** 请求 text 格式(给 LLM 读)。 */
export async function apiText(method, p, opts = {}) {
  const sep = p.includes("?") ? "&" : "?";
  const resp = await api(method, p + sep + "format=text", { ...opts, raw: true });
  const body = await resp.text();
  if (!resp.ok) throw new ApiError(resp.status, `HTTP ${resp.status}: ${body.slice(0, 200)}`);
  return body;
}
