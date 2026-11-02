import { render, screen } from "@testing-library/react";
import { EnvBanner } from "./EnvBanner";

const base = { build: "abc123def456", commit: "deadbeef", builtAt: null };

test("renders nothing in production", () => {
  const { container } = render(<EnvBanner info={{ ...base, env: "prod" }} />);
  expect(container).toBeEmptyDOMElement();
});

test("labels staging builds with the build id", () => {
  render(<EnvBanner info={{ ...base, env: "staging" }} />);
  expect(screen.getByRole("status")).toHaveTextContent("STAGING · abc123def456");
});

test("labels dev builds", () => {
  render(<EnvBanner info={{ ...base, build: "dev", env: "dev" }} />);
  expect(screen.getByRole("status")).toHaveTextContent("DEV · dev");
});
