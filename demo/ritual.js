import * as THREE from 'three';
const $ = s => document.querySelector(s);
export function createRitual({ scene, parts, camera, controls, renderer, setMode, reduced, onStart }) {
  const demo = window.detectiveDemo;
  let busy = false, time = 0, progress = 0, phase = 'idle', speaking = false, lastDraw = -1, run = 0, printStart = Infinity, stopVoice = null;
  const audio = new Audio(); audio.preload = 'auto'; audio.volume = .85;
  const voice = async (file, caption, minimum, token) => {
    $('#voice-caption').textContent = caption;
    const wait = new Promise(resolve => setTimeout(resolve, minimum));
    const ended = new Promise(resolve => {
      if (!demo.sound) return resolve();
      audio.src = `./audio/${file}`; speaking = true;
      const done = () => { clearTimeout(timeout); audio.removeEventListener('ended', done); audio.removeEventListener('error', done); if (stopVoice === done) stopVoice = null; speaking = false; resolve(); };
      const timeout = setTimeout(done, 10000);
      stopVoice = done; audio.addEventListener('ended', done, { once: true }); audio.addEventListener('error', done, { once: true });
      audio.play().catch(() => { $('#sound-toggle').textContent = '声音受限 · 字幕继续'; done(); });
    });
    await Promise.all([wait, ended]); return token === run && busy;
  };
  // Functional upper screen for the current device; printable mesh is unchanged.
  const canvas = document.createElement('canvas'); canvas.width = 480; canvas.height = 360;
  const sc = canvas.getContext('2d'), tex = new THREE.CanvasTexture(canvas); tex.colorSpace = THREE.SRGBColorSpace;
  const display = new THREE.Group(), frameMaterial = new THREE.MeshStandardMaterial({ color: '#1e292b', roughness: .7 });
  const bezel = new THREE.Mesh(new THREE.BoxGeometry(.68, .53, .07), frameMaterial);
  const panel = new THREE.Mesh(new THREE.PlaneGeometry(.61, .457), new THREE.MeshBasicMaterial({ map: tex, toneMapped: false })); panel.position.z = .036;
  const stand = new THREE.Mesh(new THREE.BoxGeometry(.10, .19, .075), frameMaterial); stand.position.set(0, -.32, 0);
  display.add(bezel, panel, stand); display.position.set(0, 1.55, .20); scene.add(display);
  function drawScreen(t) {
    sc.fillStyle = '#183137'; sc.fillRect(0, 0, 480, 360); sc.fillStyle = '#aac5b5'; sc.font = '20px monospace'; sc.textAlign = 'left'; sc.fillText('DASHAN / CASE DESK', 26, 37);
    sc.strokeStyle = '#557c73'; sc.lineWidth = 2; sc.beginPath(); sc.moveTo(26, 52); sc.lineTo(454, 52); sc.stroke();
    const blink = !reduced && Math.sin(t * 2.5) > .975;
    sc.strokeStyle = '#d9e8c6'; sc.lineWidth = 10; sc.lineCap = 'round';
    for (const x of [163, 317]) {
      sc.beginPath();
      if (blink) { sc.moveTo(x - 24, 156); sc.lineTo(x + 24, 156); }
      else if (phase === 'thinking') { sc.moveTo(x - 25, 140); sc.lineTo(x + 24, 153); }
      else if (['deducing', 'printing', 'complete'].includes(phase)) sc.arc(x, 161, 23, Math.PI, 2 * Math.PI);
      else { sc.moveTo(x, 141); sc.lineTo(x, 170); }
      sc.stroke();
    }
    sc.beginPath();
    if (speaking && !reduced) sc.ellipse(240, 222, 25, 6 + Math.abs(Math.sin(t * 16)) * 13, 0, 0, Math.PI * 2);
    else { sc.moveTo(216, 216); sc.lineTo(264, 216); } sc.stroke();
    sc.font = '25px sans-serif'; sc.textAlign = 'center'; sc.fillStyle = '#d9e8c6';
    sc.fillText({ idle: '等待新线索', observing: '先看看现场', thinking: '等等…', deducing: '原来如此！', printing: '案卷输出中', complete: '你也检查一下' }[phase], 240, 293);
    sc.fillStyle = '#92ab9e'; sc.fillRect(28, 323, 424 * (busy ? Math.min(.95, time / 20) : 1), 4); tex.needsUpdate = true;
  }
  const segments = 100, geometry = new THREE.BufferGeometry(), positions = new Float32Array((segments + 1) * 6), uv = new Float32Array((segments + 1) * 4), indices = [];
  for (let i = 0; i < segments; i++) { const a = i * 2; indices.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3)); geometry.setAttribute('uv', new THREE.BufferAttribute(uv, 2)); geometry.setIndex(indices);
  const pc = document.createElement('canvas'); pc.width = 768; pc.height = 1600;
  const ctx = pc.getContext('2d'); ctx.fillStyle = '#fffdf7'; ctx.fillRect(0, 0, 768, 1600); ctx.fillStyle = '#202628'; let y = 76;
  const line = (text, font = '32px sans-serif') => { ctx.font = font; ctx.fillText(text, 56, y); y += 54; };
  const wrap = text => { let current = ''; for (const ch of text) { if (ctx.measureText(current + ch).width > 650) { line(current); current = ''; } current += ch; } if (current) line(current); };
  line('[ DETECTIVE CAMERA ]', 'bold 39px monospace'); y += 20; line('DEMO / 001', '28px monospace'); y += 30;
  line(demo.sample.title, 'bold 42px sans-serif'); y += 25; line('[ 案情 · 虚构 ]', 'bold 32px sans-serif'); ctx.font = '32px sans-serif'; wrap(demo.sample.setup); y += 25;
  line('[ 示例现场线索 ]', 'bold 32px sans-serif'); demo.sample.clues.forEach((x, i) => line(`${i + 1}. ${x}`)); y += 25;
  line('[ 推测还原 ]', 'bold 32px sans-serif'); ctx.font = '32px sans-serif'; wrap(demo.sample.inference); y += 35; line('示例案卷 · 案情与推测纯属虚构', '27px sans-serif');
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
    if (busy) return; setMode('exterior'); onStart(); busy = true; time = 0; progress = 0; printStart = Infinity; paper.visible = false; lock(true); $('#read-case').hidden = true;
    const token = ++run; controls.autoRotate = false; $('#rotate').checked = false; camera.position.set(-1.8, 1.75, 4.2); controls.target.set(0, .60, .25);
    if (!reduced) { $('#flash').classList.add('on'); setTimeout(() => $('#flash').classList.remove('on'), 140); }
    setPhase('observing', '快门落下。先观察，不急着下结论。'); if (!await voice('01_shutter.mp3', '好，让我看看。', 2300, token)) return;
    setPhase('thinking', '示例线索：空盘、茶杯中的碎块、打开的包装。'); if (!await voice('05_wait.mp3', '如果这是故意的……目的是什么？', 5000, token)) return;
    setPhase('deducing', '如果饼干不是被吃掉，而是泡在了茶里呢？'); if (!await voice('report.mp3', '原来如此，是这么回事啊！我想我知道真相了。', 2000, token)) return;
    setPhase('printing', '正在打印案情、线索和推测还原…'); $('#voice-caption').textContent = '报告正在出来，别急着拉纸。'; paper.visible = true; printStart = time;
    camera.position.set(-1.8, 2.05, 4.7); controls.target.set(0, .35, .25);
  }
  const shutter = parts.find(p => (p.userData.part_id || '').startsWith('06_')); $('#capture').onclick = start; $('#skip').onclick = finish; $('#read-bottom').onclick = () => $('#case-dialog').showModal();
  const ray = new THREE.Raycaster(), pointer = new THREE.Vector2(); let down;
  renderer.domElement.addEventListener('pointerdown', e => { down = [e.clientX, e.clientY]; });
  renderer.domElement.addEventListener('pointerup', e => {
    if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 6 || busy) return;
    const r = renderer.domElement.getBoundingClientRect(); pointer.set((e.clientX - r.left) / r.width * 2 - 1, -(e.clientY - r.top) / r.height * 2 + 1); ray.setFromCamera(pointer, camera);
    if (paper.visible && ray.intersectObject(paper).length) $('#case-dialog').showModal(); else if (shutter && ray.intersectObject(shutter, true).length) start();
  });
  $('#capture').disabled = false; setPhase('idle', '侦探待命。按下快门，开始一次办案体验。');
  return { paper, display, get busy() { return busy; }, get progress() { return progress; }, start, setSound(enabled) { audio.muted = !enabled; }, hidePaper() { paper.visible = false; },
    update(dt) { time += dt; if (Math.floor(time * 15) !== lastDraw) { lastDraw = Math.floor(time * 15); drawScreen(time); }
      if (phase === 'printing' && busy) { updatePaper(reduced ? 1 : Math.min(1, (time - printStart) / 5)); if (progress === 1) finish(); }
    }
  };
}
