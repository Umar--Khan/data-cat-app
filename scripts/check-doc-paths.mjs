import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'

// Specs and CLAUDE.md files send the next session to files by path, so a rename that misses
// them costs it a dead end. Only root-anchored paths are checked; shorthand stays prose.
const files = execFileSync('git', ['ls-files'], { encoding: 'utf8' }).split('\n')
const known = new Set(
  files.flatMap((f) => f.split('/').map((_, i, parts) => parts.slice(0, i + 1).join('/'))),
)
const docs = files.filter((f) =>
  /^(specs\/.*|docs\/architecture|README|(backend\/|frontend\/)?CLAUDE|\.claude\/.*)\.md$/.test(f),
)
const anchored = /^(backend|frontend|specs|docs|scripts|\.github|\.claude|\.husky)\/[\w./-]*$/
const localOnly = new Set([
  'backend/.env',
  'frontend/.env.local',
  '.claude/plans/',
  '.claude/settings.local.json',
])
const missing = []
for (const doc of docs) {
  readFileSync(doc, 'utf8')
    .split('\n')
    .forEach((line, i) => {
      for (const [, path] of line.matchAll(/`([^`\s]+)`/g)) {
        if (anchored.test(path) && !localOnly.has(path) && !known.has(path.replace(/\/$/, ''))) {
          missing.push(`${doc}:${i + 1}: ${path}`)
        }
      }
    })
}
if (missing.length > 0) {
  console.error(`Docs name paths that are not in the repository:\n${missing.join('\n')}`)
  process.exitCode = 1
} else {
  console.log(`ok: ${docs.length} docs`)
}
