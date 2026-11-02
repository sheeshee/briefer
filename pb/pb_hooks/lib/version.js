// Pure helpers for the version route. No PocketBase globals here, so this
// module can be unit-tested with `node --test` (see pb/tests/).

const KNOWN_ENVS = ["prod", "staging", "verify", "dev"];

function buildInfo(rawBuildInfo, envName) {
  let parsed = {};
  try {
    parsed = rawBuildInfo ? JSON.parse(rawBuildInfo) : {};
  } catch (_) {
    parsed = {};
  }
  return {
    build: typeof parsed.build === "string" ? parsed.build : "dev",
    commit: typeof parsed.commit === "string" ? parsed.commit : "dev",
    builtAt: typeof parsed.builtAt === "string" ? parsed.builtAt : null,
    env: KNOWN_ENVS.indexOf(envName) >= 0 ? envName : "dev",
  };
}

module.exports = { buildInfo, KNOWN_ENVS };
