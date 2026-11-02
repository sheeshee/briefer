import { useEffect, useState } from "react";
import { fetchBuildInfo, type BuildInfo } from "./api";
import { EnvBanner } from "./EnvBanner";

export function App() {
  const [info, setInfo] = useState<BuildInfo | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetchBuildInfo()
      .then((i) => {
        setInfo(i);
        document.title = i.env === "prod" ? "Briefer" : `[${i.env}] Briefer`;
      })
      .catch(() => setFailed(true));
  }, []);

  return (
    <>
      {info && <EnvBanner info={info} />}
      <main className="placeholder">
        <h1>Briefer</h1>
        <p>The card stack lands in milestone M4.</p>
        <p className="build">
          {info ? `build ${info.build} · ${info.commit.slice(0, 8)}` : failed ? "version unavailable" : "…"}
        </p>
      </main>
    </>
  );
}
