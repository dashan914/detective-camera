(() => {
  const $ = s => document.querySelector(s);
  const paragraphs = [
    '《侦探相机》是一台由 AI 驱动的互动创作相机。',
    '用户按下快门后，它会拍下眼前场景，识别照片中的物件与细节，并以这些真实线索为基础，虚构一桩有逻辑、有趣味的微型案件。相机通过屏幕表情、侦探式语音和热敏打印机完成“观察—思考—推理—出案卷”的完整体验，让一张普通照片变成一份可带走的侦探报告。',
    '它不试图判断现实中的真相，而是把日常生活中被忽略的物件，转化为一场轻盈、可信、充满想象力的推理游戏。',
    '侦探相机想讨论的是：当 AI 成为创作搭档后，技术门槛不再只意味着限制；每个人都可以把一个看似天马行空的想法，做成能拍照、会思考、能说话，也能吐出纸质案卷的真实物件。'
  ];
  const sample = {
    title: '最后一块饼干失踪案',
    setup: '室友把最后一块饼干留作明早的早餐。五分钟后，盘子空了，没人承认吃过。',
    clues: ['空盘里留有饼干碎屑', '茶杯里浮着浅色碎块', '打开的饼干包装就在杯旁'],
    inference: '一种可能：有人只想蘸点茶，把饼干泡软，却聊着天忘了拿起来。饼干断在杯里，他捞不起来，也没吃进嘴，便坚持“我没吃”。所谓失踪，是早餐被提前泡成了下午茶。'
  };
  window.detectiveDemo = { sample, paragraphs, phase: 'loading', sound: true };
  document.title = 'DASHAN · 侦探相机';
  $('.wordmark').innerHTML = 'DASHAN<span>侦探相机</span>';
  document.querySelectorAll('nav a')[0].textContent = '办案体验';
  document.querySelectorAll('nav a')[1].textContent = '项目介绍';
  $('.intro h1').innerHTML = '日常看起来无事。<br>侦探不这么想。';
  $('.intro').insertAdjacentHTML('afterbegin', '<p class="eyebrow">DASHAN / DETECTIVE CAMERA</p>');
  $('.description').textContent = '按下快门。听它思考，看它露出表情，等一份属于日常的微型案卷。';
  $('#capture').innerHTML = '<span class="red-dot" aria-hidden="true"></span>按下快门 · 立案';
  $('#ritual-status').textContent = '正在准备侦探相机…';
  $('.disclaimer').textContent = '网页为预设案件演示 · 不拍摄、不上传、不触发实机';
  $('.hint').textContent = '拖动观察 · 也可以直接点击机身快门';
  $('.actions').insertAdjacentHTML('beforeend', '<button id="sound-toggle" aria-pressed="true" aria-label="关闭演示声音">声音：开</button><button id="read-case" hidden>阅读案卷</button>');
  $('.intro').insertAdjacentHTML('beforeend', '<ol class="case-steps" aria-label="办案流程"><li data-step="observing">01 观察</li><li data-step="thinking">02 思考</li><li data-step="deducing">03 推理</li><li data-step="printing">04 出卷</li></ol>');
  $('.stage').insertAdjacentHTML('beforeend', '<div class="detective-caption" role="status" aria-live="polite"><span id="phase-label">侦探待命</span><p id="voice-caption">今天有什么值得多看一眼？</p></div>');
  const sheet = () => `<article class="case-sheet"><div class="case-sheet__head"><span>DETECTIVE CAMERA</span><span>DEMO / 001</span></div><h3>${sample.title}</h3><strong>案情 · 虚构</strong><p>${sample.setup}</p><strong>示例现场线索</strong><ol>${sample.clues.map(x => `<li>${x}</li>`).join('')}</ol><strong>推测还原</strong><p>${sample.inference}</p><div class="case-sheet__seal">示例案卷 · 案情与推测纯属虚构</div></article>`;
  $('.paper-preview').outerHTML = sheet();
  $('.prose').innerHTML = '<h2 class="about-title">项目介绍</h2>' + paragraphs.map((p, i) => `<p${i === 0 ? ' class="design-intro"' : ''}>${p}</p>`).join('');
  const legacyButton = document.createElement('button'); legacyButton.id = 'read-bottom'; legacyButton.hidden = true; $('.prose').append(legacyButton);
  $('#poem-dialog').setAttribute('aria-hidden', 'true');
  document.body.insertAdjacentHTML('beforeend', `<dialog id="case-dialog" class="detective-dialog" aria-label="侦探案卷"><button id="close-case" aria-label="关闭案卷">×</button>${sheet()}</dialog>`);
  $('#close-case').onclick = () => $('#case-dialog').close();
  $('#read-case').onclick = () => $('#case-dialog').showModal();
  $('#sound-toggle').onclick = () => {
    const enabled = !window.detectiveDemo.sound;
    window.detectiveDemo.sound = enabled;
    $('#sound-toggle').setAttribute('aria-pressed', String(enabled));
    $('#sound-toggle').setAttribute('aria-label', enabled ? '关闭演示声音' : '开启演示声音');
    $('#sound-toggle').textContent = `声音：${enabled ? '开' : '关'}`;
    window.__viewer?.ritual.setSound(enabled);
  };
})();
