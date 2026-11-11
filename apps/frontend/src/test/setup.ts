import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "@/test/server";

beforeAll(() => {
  server.listen({ onUnhandledFrame: "bypass" });
});

afterEach(() => {
  server.resetHandlers();
  cleanup();
  try {
    window.localStorage.clear();
  } catch {
    // Ignore storage errors in non-DOM contexts
  }
});

afterAll(() => {
  server.close();
});
