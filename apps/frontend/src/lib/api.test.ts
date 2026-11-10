import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import {
  AUTH_EXPIRED_EVENT,
  ApiError,
  TOKEN_STORAGE_KEY,
  api,
  getStoredToken,
  setStoredToken,
} from "@/lib/api";
import { server } from "@/test/server";

describe("api client", () => {
  it("sends Authorization: Bearer when a token exists in localStorage", async () => {
    setStoredToken("jwt-secret-token");
    let capturedAuth: string | null = null;

    server.use(
      http.get("*/api/v1/agents", ({ request }) => {
        capturedAuth = request.headers.get("authorization");
        return HttpResponse.json([]);
      }),
    );

    await api.agents.list();

    expect(capturedAuth).toBe("Bearer jwt-secret-token");
  });

  it("clears token and dispatches auth:expired on 401", async () => {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, "expired-token");
    const onExpired = vi.fn();
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);

    server.use(
      http.get("*/api/v1/agents", () =>
        HttpResponse.json({ error: "unauthorized" }, { status: 401 }),
      ),
    );

    await expect(api.agents.list()).rejects.toThrow(ApiError);
    expect(getStoredToken()).toBeNull();
    expect(onExpired).toHaveBeenCalledTimes(1);

    window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
  });
});
