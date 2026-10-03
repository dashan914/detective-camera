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
  const caseExact = await page.evaluate(() => {
    const s = window.detectiveDemo.sample;
    return s.title === '衣服真正的主人' && s.setup === '我发现衣服的肩膀上，总有两个鼓包。\n于是，我请它调查一下。没想到，它先调查了我。' && s.clues.join('') === '衣服肩部有两处凸起，位置正好对应衣架的两端。' && s.inference === '衣架穿了它太久，这件衣服早就记住了衣架的样子。\n衣服真正的主人是衣架。\n而你，极有可能是个小偷。' && s.afterword === '第一次使用，它就把我从侦探变成了嫌疑人。' && !document.body.textContent.includes('饼干');
  });
  if (!caseExact) throw Error('Approved case text mismatch');
  await page.screenshot({ path: '/private/tmp/detective-demo-idle.png' });
  await page.click('#capture');
  await page.waitForFunction(() => window.detectiveDemo.phase === 'thinking');
  await page.screenshot({ path: '/private/tmp/detective-demo-thinking.png' });
  await page.waitForFunction(() => window.detectiveDemo.phase === 'printing' && window.__viewer.ritual.audioState.speaking && !window.__viewer.ritual.audioState.paused);
  const printingAudio = await page.evaluate(() => window.__viewer.ritual.audioState.src);
  if (!printingAudio.endsWith('/audio/clothes-case-clean.mp3')) throw Error(`Wrong printing clip: ${printingAudio}`);
  const narrationCaptionExact = await page.evaluate(() => document.querySelector('#voice-caption').textContent === window.detectiveDemo.sample.inference);
  if (!narrationCaptionExact) throw Error('Narration caption is not the approved inference');
  const captionFits = () => {
    const caption = document.querySelector('.detective-caption');
    const text = document.querySelector('#voice-caption');
    const card = caption.getBoundingClientRect(), stage = caption.parentElement.getBoundingClientRect();
    const view = document.querySelector('#viewport').getBoundingClientRect();
    const range = document.createRange(); range.selectNodeContents(text);
    return card.top >= stage.top && card.right <= stage.right && card.left >= stage.left && card.bottom <= view.top + 1 &&
      view.height > 200 && text.scrollWidth <= text.clientWidth && Array.from(range.getClientRects()).every(r =>
        r.left >= card.left && r.right <= card.right && r.top >= card.top && r.bottom <= card.bottom);
  };
  if (!await page.evaluate(captionFits)) throw Error('Printing caption overlaps or leaves its card');
  await page.screenshot({ path: '/private/tmp/detective-demo-printing-voice.png' });
  await page.waitForFunction(() => window.detectiveDemo.phase === 'printing' && window.__viewer.ritual.audioState.currentTime > window.__viewer.ritual.audioState.duration * .70);
  const narrationUncut = await page.evaluate(() => !window.__viewer.ritual.audioState.paused && window.__viewer.ritual.audioState.speaking && window.__viewer.ritual.progress > .65 && window.__viewer.ritual.progress < 1 && Math.abs(window.__viewer.ritual.progress - window.__viewer.ritual.audioState.currentTime / window.__viewer.ritual.audioState.duration) < .04);
  if (!narrationUncut) throw Error('Case narration or print progress interrupted before the ending');
  await page.waitForFunction(() => window.detectiveDemo.phase === 'complete', null, { timeout: 40000 });
  const narrationCompleted = await page.evaluate(() => window.__viewer.ritual.audioState.ended && window.__viewer.ritual.audioState.currentTime > 8 && window.__viewer.ritual.audioState.currentTime < 10);
  if (!narrationCompleted) throw Error('Paper completed before narration finished');
  await page.screenshot({ path: '/private/tmp/detective-demo-printed.png' });
  await page.click('#read-case');
  if (!(await page.locator('#case-dialog').evaluate(e => e.open))) throw Error('Case dialog failed');
  await page.screenshot({ path: '/private/tmp/detective-clothes-case.png' });
  await page.keyboard.press('Escape');
  await page.click('#sound-toggle');
  await page.click('#capture'); await page.click('#skip');
  await page.click('#capture'); await page.click('#skip');
  await page.waitForTimeout(2500);
  if (await page.evaluate(() => window.detectiveDemo.phase !== 'complete')) throw Error('Cancelled sequence resumed');
  await page.click('[data-mode="inside"]'); await page.click('[data-mode="explode"]'); await page.click('[data-mode="exterior"]');
  await page.setViewportSize({ width: 390, height: 844 });
  for (const width of [320, 390, 850, 1280]) {
    await page.setViewportSize({ width, height: 844 });
    await page.evaluate(() => document.querySelector('#voice-caption').textContent = window.detectiveDemo.sample.inference);
    await page.waitForTimeout(100);
    if (!await page.evaluate(captionFits)) throw Error(`Caption does not fit at ${width}px`);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: '/private/tmp/detective-demo-mobile.png', fullPage: true });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  const introExact = await page.evaluate(() => window.detectiveDemo.paragraphs.every((p, i) => document.querySelectorAll('.prose p')[i].textContent === p));
  await page.emulateMedia({ reducedMotion: 'reduce' }); await page.reload();
  await page.waitForFunction(() => window.__viewerReady && window.detectiveDemo.phase === 'idle'); await page.click('#sound-toggle'); await page.click('#capture');
  await page.waitForFunction(() => window.detectiveDemo.phase === 'complete', null, { timeout: 20000 });
  console.log(JSON.stringify({ errors, failedRequests, overflow, introExact, caseExact, printingAudio, narrationCaptionExact, captionContained: true, narrationUncut, narrationCompleted, screen, reducedMotionComplete: true }));
  await browser.close();
  if (errors.length || failedRequests.length || overflow || !introExact) process.exit(1);
})().catch(e => { console.error(e); process.exit(1); });
