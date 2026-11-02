/// <reference path="../pb_data/types.d.ts" />

// GET /api/briefer/version -> { build, commit, builtAt, env }
// Used by the frontend's environment banner and by deploy/smoke.sh to check
// that the expected build is live.
routerAdd("GET", "/api/briefer/version", (e) => {
  const { buildInfo } = require(`${__hooks}/lib/version.js`);
  let raw = "";
  try {
    raw = toString($os.readFile(`${__hooks}/../BUILD_INFO.json`));
  } catch (_) {
    raw = "";
  }
  return e.json(200, buildInfo(raw, $os.getenv("BRIEFER_ENV")));
});
