const test = require("node:test");
const assert = require("node:assert/strict");
const { buildInfo } = require("../pb_hooks/lib/version.js");

test("buildInfo merges BUILD_INFO json with the environment name", () => {
  const info = buildInfo('{"build":"abc123def456","commit":"deadbeef","builtAt":"2026-11-02T00:00:00Z"}', "staging");
  assert.deepEqual(info, {
    build: "abc123def456",
    commit: "deadbeef",
    builtAt: "2026-11-02T00:00:00Z",
    env: "staging",
  });
});

test("buildInfo falls back to dev values when BUILD_INFO is missing or invalid", () => {
  assert.deepEqual(buildInfo("", ""), { build: "dev", commit: "dev", builtAt: null, env: "dev" });
  assert.deepEqual(buildInfo("not json", "prod"), { build: "dev", commit: "dev", builtAt: null, env: "prod" });
});

test("buildInfo only accepts known environment names", () => {
  assert.equal(buildInfo("", "evil<script>").env, "dev");
  for (const env of ["prod", "staging", "verify", "dev"]) {
    assert.equal(buildInfo("", env).env, env);
  }
});
