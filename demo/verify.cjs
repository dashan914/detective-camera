const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [], phases = [], failedRequests = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('response', r => { if (r.status() >= 400) failedRequests.push(r.url()); });
  await page.goto(process.env.DEMO_URL || 'http://127.0.0.1:8894/');
  await page.waitForFunction(() => window.__viewerReady && window.detectiveDemo.phase === 'idle');
  const screen = await page.evaluate(() => {
    const { parts, ritual } = window.__viewer;
    const display = parts.find(p => p.userData.role === 'display_surface');
    let mesh; display?.traverse(o => { if (o.isMesh) mesh = o; });
    const position = mesh?.geometry.attributes.position;
    const ys = position ? Array.from({ length: position.count }, (_, i) => position.getY(i)) : [];
    return { printParts: parts.filter(p => p.userData.role === 'print_part').length,
      physicalSurface: display === ritual.display, worldTopY: Math.max(...ys) * 10,
      width: mesh?.material.map.image.width, height: mesh?.material.map.image.height,
      flipY: mesh?.material.map.flipY };
  });
  if (!screen.physicalSurface || Math.abs(screen.worldTopY - 1.1972) > .001 || screen.width !== 284 || screen.height !== 240 || screen.flipY || screen.printParts !== 27) throw Error(`Physical screen mismatch: ${JSON.stringify(screen)}`);
  await page.screenshot({ path: '/private/tmp/detective-demo-idle.png' });
  await page.click('#capture');
  await page.waitForFunction(() => window.detectiveDemo.phase === 'thinking');
  await page.screenshot({ path: '/private/tmp/detective-demo-thinking.png' });
  await page.waitForFunction(() => window.detectiveDemo.phase === 'complete', null, { timeout: 40000 });
  await page.screenshot({ path: '/private/tmp/detective-demo-printed.png' });
  await page.click('#read-case');
  if (!(await page.locator('#case-dialog').evaluate(e => e.open))) throw Error('Case dialog failed');
  await page.keyboard.press('Escape');
  await page.click('#sound-toggle');
  await page.click('#capture'); await page.click('#skip');
  await page.click('#capture'); await page.click('#skip');
  await page.waitForTimeout(2500);
  if (await page.evaluate(() => window.detectiveDemo.phase !== 'complete')) throw Error('Cancelled sequence resumed');
  await page.click('[data-mode="inside"]'); await page.click('[data-mode="explode"]'); await page.click('[data-mode="exterior"]');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: '/private/tmp/detective-demo-mobile.png', fullPage: true });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  const introExact = await page.evaluate(() => window.detectiveDemo.paragraphs.every((p, i) => document.querySelectorAll('.prose p')[i].textContent === p));
  await page.emulateMedia({ reducedMotion: 'reduce' }); await page.reload();
  await page.waitForFunction(() => window.__viewerReady && window.detectiveDemo.phase === 'idle'); await page.click('#sound-toggle'); await page.click('#capture');
  await page.waitForFunction(() => window.detectiveDemo.phase === 'complete', null, { timeout: 20000 });
  console.log(JSON.stringify({ errors, failedRequests, overflow, introExact, screen, reducedMotionComplete: true }));
  await browser.close();
  if (errors.length || failedRequests.length || overflow || !introExact) process.exit(1);
})().catch(e => { console.error(e); process.exit(1); });
