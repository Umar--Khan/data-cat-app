import { constants, copyFile } from 'node:fs/promises'
import { join } from 'node:path'

const backend = join(import.meta.dirname, '..', 'backend')

try {
  await copyFile(join(backend, '.env.example'), join(backend, '.env'), constants.COPYFILE_EXCL)
  console.log('Created backend/.env from backend/.env.example')
} catch (error) {
  if (error.code !== 'EEXIST') throw error
  console.log('backend/.env already exists; left unchanged')
}
