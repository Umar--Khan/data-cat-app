// Dedicated ports, so Playwright never talks to a running `pnpm dev`, whose API may hold a real
// Anthropic key (specs/quality-gates.md, Ports).
export const apiPort = 8001
export const webPort = 4173

export const apiUrl = `http://localhost:${String(apiPort)}`
export const webUrl = `http://localhost:${String(webPort)}`
