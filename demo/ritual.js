import * as THREE from 'three';
const $ = s => document.querySelector(s);
export function createRitual({ scene, parts, camera, controls, renderer, setMode, reduced, onStart }) {
  const demo = window.detectiveDemo;
  let busy = false, time = 0, progress = 0, phase = 'idle', speaking = false, lastDraw = -1, run = 0, printStart = Infinity, printDuration = 5, printVoiceDone = false, stopVoice = null;
  const audio = new Audio(); audio.preload = 'auto'; audio.volume = .85;
  const voice = async (file, caption, minimum, token, maxWait = 10000) => {
    $('#voice-caption').textContent = caption;
    const wait = new Promise(resolve => setTimeout(resolve, minimum));
    const ended = new Promise(resolve => {
      if (!demo.sound) return resolve();
      audio.src = `./audio/${file}`; speaking = true;
      const done = () => { clearTimeout(timeout); audio.removeEventListener('ended', done); audio.removeEventListener('error', done); if (stopVoice === done) stopVoice = null; speaking = false; resolve(); };
      const timeout = setTimeout(() => { audio.pause(); done(); }, maxWait);
      stopVoice = done; audio.addEventListener('ended', done, { once: true }); audio.addEventListener('error', done, { once: true });
      audio.play().catch(() => { $('#sound-toggle').textContent = '声音受限 · 字幕继续'; done(); });
    });
    await Promise.all([wait, ended]); return token === run && busy;
  };
  // Use the physical V33 active-area mesh, flush inside the existing top opening.
  // Every bitmap is rendered from DetectiveDisplay.cpp, not a web reinterpretation.
  const canvas = document.createElement('canvas'); canvas.width = 284; canvas.height = 240;
  const sc = canvas.getContext('2d'), tex = new THREE.CanvasTexture(canvas); tex.colorSpace = THREE.SRGBColorSpace; tex.flipY = false;
  sc.imageSmoothingEnabled = false;
  const display = parts.find(p => p.userData.role === 'display_surface');
  if (!display) throw new Error('V33 top screen surface is missing');
  display.traverse(mesh => { if (mesh.isMesh) { mesh.material = new THREE.MeshBasicMaterial({ map: tex, toneMapped: false }); mesh.castShadow = false; mesh.receiveShadow = false; } });
  const frames = {}, states = ['ready', 'capturing', 'deducing', 'printing']; let screenReady = false;
  const frameLoads = states.flatMap(state => ['silent', 'talking'].map(mouth => new Promise((resolve, reject) => {
    const img = new Image(), key = `${state}-${mouth}`;
    img.onload = () => { frames[key] = img; resolve(); };
    img.onerror = () => reject(new Error(`Screen animation failed: ${key}`));
    img.src = `./screen-frames/${key}.png`;
  })));
  function drawScreen(t) {
    const state = { idle: 'ready', observing: 'capturing', thinking: 'deducing', deducing: 'deducing', printing: 'printing', complete: 'ready' }[phase];
    const img = frames[`${state}-${speaking && !reduced ? 'talking' : 'silent'}`];
    if (!img) return;
    const frame = reduced ? 2 : Math.floor(t * 1000 / 120) % 36;
    sc.drawImage(img, (frame % 8) * 284, Math.floor(frame / 8) * 240, 284, 240, 0, 0, 284, 240); tex.needsUpdate = true;
  }
  const segments = 100, geometry = new THREE.BufferGeometry(), positions = new Float32Array((segments + 1) * 6), uv = new Float32Array((segments + 1) * 4), indices = [];
  for (let i = 0; i < segments; i++) { const a = i * 2; indices.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3)); geometry.setAttribute('uv', new THREE.BufferAttribute(uv, 2)); geometry.setIndex(indices);
  const pc = document.createElement('canvas'); pc.width = 768; pc.height = 1600;
  const ctx = pc.getContext('2d'); ctx.fillStyle = '#fffdf7'; ctx.fillRect(0, 0, 768, 1600); ctx.fillStyle = '#202628'; let y = 76;
  const line = (text, font = '32px sans-serif') => { ctx.font = font; ctx.fillText(text, 56, y); y += 54; };
  const wrap = (text, font = '32px sans-serif') => { ctx.font = font; for (const paragraph of text.split('\n')) { let current = ''; for (const ch of paragraph) { if (ctx.measureText(current + ch).width > 650) { line(current, font); current = ''; } current += ch; } if (current) line(current, font); } };
  line('[ DETECTIVE CAMERA ]', 'bold 39px monospace'); y += 20; line('DEMO / 001', '28px monospace'); y += 30;
  line(demo.sample.title, 'bold 42px sans-serif'); y += 25; line('[ 案情 · 虚构 ]', 'bold 32px sans-serif'); ctx.font = '32px sans-serif'; wrap(demo.sample.setup); y += 25;
  line('[ 现场线索 ]', 'bold 32px sans-serif'); demo.sample.clues.forEach(x => wrap(x)); y += 25;
  line('[ 侦探推测 ]', 'bold 32px sans-serif'); wrap(demo.sample.inference); y += 35; wrap(demo.sample.afterword, '28px sans-serif'); y += 35; line('示例案卷 · 案情与推测纯属虚构', '27px sans-serif');
  const pt = new THREE.CanvasTexture(pc); pt.colorSpace = THREE.SRGBColorSpace;
  const paper = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ map: pt, side: THREE.DoubleSide, toneMapped: false })); paper.visible = false; paper.frustumCulled = false; scene.add(paper);
  function updatePaper(p) {
    progress = p;
    for (let i = 0; i <= segments; i++) {
      const s = i / segments * .16 * p, bend = Math.max(0, s - .033);
      for (let j = 0; j < 2; j++) {
        const n = i * 2 + j; positions[n * 3] = (j ? .029 : -.029) * 10;
        positions[n * 3 + 1] = (.014 - bend * .73) * 10; positions[n * 3 + 2] = (.061 + Math.min(s, .033) + .040 * (1 - Math.exp(-bend / .040))) * 10;
        uv[n * 2] = j; uv[n * 2 + 1] = 1 - i / segments * p;
      }
    }
    geometry.attributes.position.needsUpdate = true; geometry.attributes.uv.needsUpdate = true; geometry.computeVertexNormals(); geometry.computeBoundingSphere();
  }
  function setPhase(value, caption) {
    phase = value; demo.phase = value; $('#phase-label').textContent = { idle: '侦探待命', observing: '观察现场', thinking: '梳理线索', deducing: '形成推测', printing: '正在出卷', complete: '案卷已完成' }[value]; $('#ritual-status').textContent = caption;
    const order = ['observing', 'thinking', 'deducing', 'printing'];
    document.querySelectorAll('[data-step]').forEach(el => { el.classList.toggle('active', el.dataset.step === value); el.classList.toggle('done', order.indexOf(el.dataset.step) < order.indexOf(value) || value === 'complete'); }); drawScreen(time);
  }
  function lock(value) { document.querySelectorAll('.explore button,.explore input,.explore select').forEach(el => { el.disabled = value; }); controls.enabled = !value; $('#capture').disabled = value; $('#skip').hidden = !value; }
  function finish() {
    if (!busy) return; run++; audio.pause(); stopVoice?.(); speaking = false; busy = false; paper.visible = true; updatePaper(1); lock(false);
    setPhase('complete', '案卷已出。真实线索，虚构故事。'); $('#voice-caption').textContent = '推测在纸上了，你也检查一下。'; $('#read-case').hidden = false;
    $('#capture').innerHTML = '<span class="red-dot" aria-hidden="true"></span>再体验一次'; $('#flash').classList.remove('on');
  }
  async function start() {
    if (busy || !screenReady) return; setMode('exterior'); onStart(); busy = true; time = 0; progress = 0; printStart = Infinity; printVoiceDone = false; paper.visible = false; lock(true); $('#read-case').hidden = true;
    const token = ++run; controls.autoRotate = false; $('#rotate').checked = false; camera.position.set(-1.6, 2.9, 3.5); controls.target.set(0, .60, .15);
    if (!reduced) { $('#flash').classList.add('on'); setTimeout(() => $('#flash').classList.remove('on'), 140); }
    setPhase('observing', '快门落下。先观察，不急着下结论。'); if (!await voice('01_shutter.mp3', '好，让我看看。', 2300, token)) return;
    setPhase('thinking', '现场线索：肩部两处凸起，正好对应衣架的两端。'); if (!await voice('05_wait.mp3', '如果这是故意的……目的是什么？', 5000, token)) return;
    setPhase('deducing', '衣服记住了衣架的样子，谁才是真正的主人？'); if (!await voice('report.mp3', '原来如此，是这么回事啊！我想我知道真相了。', 2000, token)) return;
    setPhase('printing', '正在打印并朗读《衣服真正的主人》的推理…'); paper.visible = true; printStart = time;
    printDuration = demo.sound ? Math.max(5, demo.sample.narration.durationSeconds) : 5;
    camera.position.set(-1.8, 3.1, 4.5); controls.target.set(0, .35, .25);
    // Read the exact approved inference, using audio playback as the print clock.
    void voice(demo.sample.narration.file, demo.sample.inference, 0, token, Math.ceil(printDuration * 1000) + 15000).then(active => { if (active) printVoiceDone = true; });
  }
  const shutter = parts.find(p => (p.userData.part_id || '').startsWith('06_')); $('#capture').onclick = start; $('#skip').onclick = finish; $('#read-bottom').onclick = () => $('#case-dialog').showModal();
  const ray = new THREE.Raycaster(), pointer = new THREE.Vector2(); let down;
  renderer.domElement.addEventListener('pointerdown', e => { down = [e.clientX, e.clientY]; });
  renderer.domElement.addEventListener('pointerup', e => {
    if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 6 || busy) return;
    const r = renderer.domElement.getBoundingClientRect(); pointer.set((e.clientX - r.left) / r.width * 2 - 1, -(e.clientY - r.top) / r.height * 2 + 1); ray.setFromCamera(pointer, camera);
    if (paper.visible && ray.intersectObject(paper).length) $('#case-dialog').showModal(); else if (shutter && ray.intersectObject(shutter, true).length) start();
  });
  Promise.all(frameLoads).then(() => { screenReady = true; $('#capture').disabled = false; setPhase('idle', '侦探待命。按下快门，开始一次办案体验。'); }).catch(error => { console.error(error); $('#ritual-status').textContent = '屏幕动画未加载，请刷新重试。'; });
  return { paper, display, get busy() { return busy; }, get progress() { return progress; }, get audioState() { return { speaking, src: audio.currentSrc || audio.src, paused: audio.paused, ended: audio.ended, currentTime: audio.currentTime, duration: audio.duration }; }, start, setSound(enabled) { audio.muted = !enabled; }, hidePaper() { paper.visible = false; },
    update(dt) { time += dt; if (Math.floor(time * 15) !== lastDraw) { lastDraw = Math.floor(time * 15); drawScreen(time); }
      if (phase === 'printing' && busy) {
        const isCaseAudio = printDuration > 5 && audio.currentSrc.endsWith(`/audio/${demo.sample.narration.file}`);
        const clock = isCaseAudio && !audio.paused && Number.isFinite(audio.duration) && audio.duration > 0 ? audio.currentTime / audio.duration : (time - printStart) / printDuration;
        updatePaper(reduced || (isCaseAudio && audio.ended && printVoiceDone) ? 1 : Math.min(1, clock));
        if (progress === 1 && printVoiceDone) finish();
      }
    }
  };
}
