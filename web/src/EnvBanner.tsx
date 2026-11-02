import type { BuildInfo } from "./api";

// A loud, always-visible strip so a staging tab can never be mistaken for prod.
export function EnvBanner({ info }: { info: BuildInfo }) {
  if (info.env === "prod") return null;
  return (
    <div role="status" className={`env-banner env-${info.env}`}>
      {info.env.toUpperCase()} · {info.build}
    </div>
  );
}
