import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const viteCli = fileURLToPath(new URL('../node_modules/vite/bin/vite.js', import.meta.url))
const playwrightCli = fileURLToPath(new URL('../node_modules/@playwright/test/cli.js', import.meta.url))
const preview = spawn(process.execPath, [viteCli, 'preview', '--host', '127.0.0.1'], {
  stdio: 'inherit',
})

const deadline = Date.now() + 30_000
try {
  while (true) {
    try {
      const response = await fetch('http://127.0.0.1:4173')
      if (response.ok) break
    } catch {
      if (preview.exitCode !== null) throw new Error('Vite preview exited before it became ready.')
    }
    if (Date.now() >= deadline) throw new Error('Vite preview did not become ready within 30 seconds.')
    await new Promise((resolve) => setTimeout(resolve, 100))
  }

  const tests = spawn(process.execPath, [playwrightCli, 'test', ...process.argv.slice(2)], {
    stdio: 'inherit',
  })
  const exitCode = await new Promise((resolve, reject) => {
    tests.once('error', reject)
    tests.once('exit', (code) => resolve(code ?? 1))
  })
  process.exitCode = exitCode
} finally {
  preview.kill()
}
