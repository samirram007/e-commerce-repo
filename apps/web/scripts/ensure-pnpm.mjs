/**
 * Dependency-free guard: fail any install that is not run with pnpm.
 *
 * Wired as `preinstall`, so `npm install` / `yarn install` abort with a clear
 * message while `pnpm install` (and `corepack pnpm install`) proceed. pnpm sets
 * `npm_config_user_agent` to a string starting with `pnpm/`; npm uses `npm/`.
 */
const agent = process.env.npm_config_user_agent ?? "";

// The package manager's user agent always leads with "<name>/<version>"; allow
// an empty agent so unusual (e.g. programmatic) invocations are not blocked.
if (agent && !agent.startsWith("pnpm/")) {
  const detected = agent.split(" ")[0] ?? "unknown";
  console.error(
    [
      "",
      `\u2716 This project must be installed with pnpm (detected: ${detected}).`,
      "  Run:  corepack enable && pnpm install",
      "",
    ].join("\n"),
  );
  process.exit(1);
}
