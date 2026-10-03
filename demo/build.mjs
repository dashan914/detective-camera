import { createRequire } from 'node:module';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
process.chdir(fileURLToPath(new URL('.', import.meta.url)));
const require = createRequire(import.meta.url);
let build;
try { ({ build } = require('esbuild')); } catch { ({ build } = require('../../VERSE_Printable/viewer_v11/node_modules/esbuild')); }
await build({ entryPoints: ['viewer.js'], bundle: true, format: 'iife', minify: true, outfile: 'viewer.bundle.js', legalComments: 'eof', nodePaths: ['../../VERSE_Printable/viewer_v11/node_modules'] });
const template = fs.readFileSync('index.template.html', 'utf8');
const bundle = fs.readFileSync('viewer.bundle.js', 'utf8').replaceAll('</script', '<\\/script');
fs.writeFileSync('index.html', template.replace('__VIEWER_BUNDLE__', () => bundle));
