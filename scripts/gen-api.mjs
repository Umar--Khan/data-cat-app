import { spawnSync } from 'node:child_process'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, relative, resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const committed = {
  openapi: join(root, 'frontend', 'openapi.json'),
  schema: join(root, 'frontend', 'src', 'lib', 'api', 'schema.gen.ts'),
}

function run(command, args, stdio) {
  const { status, error } = spawnSync(command, args, { cwd: root, stdio })
  if (error) throw error
  if (status !== 0) throw new Error(`${command} ${args.join(' ')} exited with ${status}`)
}

// Absolute paths, because both commands run from their own package directory.
function generate({ openapi, schema }, stdio = 'inherit') {
  run('uv', ['run', '--directory', 'backend', 'catalogue-openapi', '--output', openapi], stdio)
  run(
    'pnpm',
    [
      '--filter',
      'frontend',
      '--fail-if-no-match',
      'exec',
      'openapi-typescript',
      openapi,
      '-o',
      schema,
      '--root-types',
      '--root-types-no-schema-prefix',
    ],
    stdio,
  )
}

async function readIfPresent(path) {
  try {
    return await readFile(path)
  } catch (error) {
    if (error.code === 'ENOENT') return null
    throw error
  }
}

async function check() {
  const dir = await mkdtemp(join(tmpdir(), 'gen-api-'))
  try {
    const fresh = { openapi: join(dir, 'openapi.json'), schema: join(dir, 'schema.gen.ts') }
    // openapi-typescript announces each write on stdout, here with throwaway temporary paths.
    generate(fresh, ['ignore', 'ignore', 'inherit'])
    const stale = []
    for (const key of Object.keys(committed)) {
      const [expected, actual] = await Promise.all([
        readIfPresent(committed[key]),
        readFile(fresh[key]),
      ])
      if (!expected?.equals(actual)) stale.push(relative(root, committed[key]))
    }
    return stale
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
}

try {
  if (process.argv.includes('--check')) {
    const stale = await check()
    if (stale.length > 0) {
      console.error(
        `Generated API files are out of date with the backend: ${stale.join(', ')}.\nRun \`pnpm gen:api\` and commit the result.`,
      )
      process.exitCode = 1
    } else {
      console.log('Generated API files match the backend OpenAPI document.')
    }
  } else {
    generate(committed)
  }
} catch (error) {
  console.error(`gen:api failed: ${error.message}`)
  process.exitCode = 1
}
