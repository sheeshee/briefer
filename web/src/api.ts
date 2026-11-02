export type Env = "prod" | "staging" | "verify" | "dev";

export interface BuildInfo {
  build: string;
  commit: string;
  builtAt: string | null;
  env: Env;
}

export async function fetchBuildInfo(): Promise<BuildInfo> {
  const res = await fetch("/api/briefer/version", { cache: "no-store" });
  if (!res.ok) throw new Error(`version endpoint returned ${res.status}`);
  return (await res.json()) as BuildInfo;
}
