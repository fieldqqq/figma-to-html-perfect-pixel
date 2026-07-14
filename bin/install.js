#!/usr/bin/env node
/* Installs the figma-to-html-pixel-perfect skill for Claude Code.
 *
 *   npx figma-to-html-pixel-perfect            → ~/.claude/skills/… (personal, all projects)
 *   npx figma-to-html-pixel-perfect --project  → ./.claude/skills/… (this project only)
 *
 * Copies SKILL.md, scripts/ and references/ from this package. No dependencies.
 */
const fs = require('fs');
const path = require('path');
const os = require('os');

const SKILL = 'figma-to-html-pixel-perfect';
const SRC = path.join(__dirname, '..');
const project = process.argv.includes('--project');
const destRoot = project
  ? path.join(process.cwd(), '.claude', 'skills')
  : path.join(os.homedir(), '.claude', 'skills');
const dest = path.join(destRoot, SKILL);

function copyDir(src, dst) {
  fs.mkdirSync(dst, { recursive: true });
  for (const e of fs.readdirSync(src, { withFileTypes: true })) {
    if (['node_modules', '.git', 'bin', 'package.json'].includes(e.name)) continue;
    const s = path.join(src, e.name), d = path.join(dst, e.name);
    e.isDirectory() ? copyDir(s, d) : fs.copyFileSync(s, d);
  }
}

const existed = fs.existsSync(path.join(dest, 'SKILL.md'));
copyDir(SRC, dest);
fs.chmodSync(dest, 0o755);

console.log(`${existed ? 'Updated' : 'Installed'} ${SKILL} → ${dest}
`);
console.log(`Next steps:
  1. Figma token (one-time):
       echo 'YOUR_TOKEN' > ~/.figma_token && chmod 600 ~/.figma_token
     (figma.com → Settings → Security → Personal access tokens, scope "File content: Read")
  2. Restart your Claude Code session — the skill is picked up automatically,
     or invoke it with /${SKILL}
  3. Docs: ${dest}/README.md`);
