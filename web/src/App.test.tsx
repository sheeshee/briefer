import { render, screen } from "@testing-library/react";
import { App } from "./App";

afterEach(() => {
  vi.unstubAllGlobals();
  document.title = "";
});

test("shows the environment banner and prefixes the title outside prod", async () => {
  vi.stubGlobal("fetch", vi.fn(async () =>
    new Response(JSON.stringify({ build: "abc123def456", commit: "c", builtAt: null, env: "staging" })),
  ));
  render(<App />);
  expect(await screen.findByRole("status")).toHaveTextContent("STAGING");
  expect(document.title).toBe("[staging] Briefer");
  expect(screen.getByRole("heading", { name: "Briefer" })).toBeInTheDocument();
});

test("keeps working when the version endpoint is unreachable", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("network down"); }));
  render(<App />);
  expect(await screen.findByText(/version unavailable/i)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Briefer" })).toBeInTheDocument();
});
