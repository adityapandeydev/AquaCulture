// Fails when an animation or transition uses a property that forces layout, or names no property.
import { readFileSync, readdirSync } from 'node:fs'

const allowed = new Set(['transform', 'opacity', 'clip-path', 'color', 'background-color', 'border-color', 'overlay', 'display'])
const descriptors = new Set(['animation-timing-function'])
const files = [...readdirSync('src/styles').filter((f) => f.endsWith('.css')).map((f) => 'src/styles/' + f), 'index.html']
const problems = []

for (const file of files) {
  const text = readFileSync(file, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
  for (const [, name, body] of text.matchAll(/@keyframes\s+([\w-]+)\s*\{((?:[^{}]*\{[^{}]*\})*[^{}]*)\}/g))
    for (const [, property] of body.matchAll(/(?:^|[;{])\s*([a-z-]+)\s*:/g))
      if (!allowed.has(property) && !descriptors.has(property)) problems.push(`${file}: keyframes ${name} move ${property}`)
  for (const [, value] of text.matchAll(/[;{\s]transition\s*:\s*([^;}]+)/g))
    for (const part of value.replace(/\([^)]*\)/g, '').split(',')) {
      const property = part.trim().split(/\s+/)[0]
      if (!allowed.has(property)) problems.push(`${file}: transition of ${property}`)
    }
  if (/will-change/.test(text)) problems.push(`${file}: will-change is permanent here, remove it`)
}

if (problems.length) {
  console.error(problems.join('\n'))
  process.exit(1)
}
console.log(`motion: ${files.length} files use only compositor-friendly properties`)
