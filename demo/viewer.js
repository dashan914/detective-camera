import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {DRACOLoader} from 'three/addons/loaders/DRACOLoader.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {createRitual} from './ritual.js';
const $=s=>document.querySelector(s), rootEl=$('#viewport'), reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
const scene=new THREE.Scene(), camera=new THREE.PerspectiveCamera(34,1,.005,60);
let renderer,controls,model,parts=[],mode='exterior',explode=0,targetExplode=0,ritual;
function showStaticPreview(){
  $('#loading').classList.add('static-preview');
  $('#loading').innerHTML='<strong>当前浏览器不支持 3D 预览</strong><p>请用 Safari 或 Chrome 打开，即可查看顶部嵌入屏幕的侦探相机。</p>';
}
try{renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,preserveDrawingBuffer:true});}catch(e){showStaticPreview();throw e;}
renderer.setPixelRatio(Math.min(devicePixelRatio,1.8));renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=.95;renderer.outputColorSpace=THREE.SRGBColorSpace;
renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;rootEl.appendChild(renderer.domElement);
renderer.domElement.setAttribute('aria-label','侦探相机三维预览；可拖动观察或使用观察按钮');
controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=!reduced;controls.dampingFactor=.09;controls.minDistance=1;controls.maxDistance=12;controls.autoRotateSpeed=.65;controls.target.set(0,.6,0);
const pmrem=new THREE.PMREMGenerator(renderer),room=new RoomEnvironment();scene.environment=pmrem.fromScene(room,.04).texture;scene.environmentIntensity=.65;room.dispose();
scene.add(new THREE.HemisphereLight(0xfff7e7,0x686b6b,.35));
const key=new THREE.DirectionalLight(0xfff7e8,1.8);key.position.set(-3,5,4);key.castShadow=true;key.shadow.mapSize.set(2048,2048);key.shadow.camera.left=-3;key.shadow.camera.right=3;key.shadow.camera.top=3;key.shadow.camera.bottom=-3;key.shadow.normalBias=.002;scene.add(key);
const fill=new THREE.DirectionalLight(0xe5f1ff,.65);fill.position.set(3,2,-2);scene.add(fill);
const floor=new THREE.Mesh(new THREE.PlaneGeometry(200,200),new THREE.ShadowMaterial({opacity:.13}));floor.rotation.x=-Math.PI/2;floor.position.y=-.008;floor.receiveShadow=true;scene.add(floor);
scene.background=new THREE.Color('#f5f5f2');
const viewVectors={front:[0,.25,4.2],back:[0,.25,-4.2],left:[-4.2,.1,0],right:[4.2,.1,0],top:[0,4.2,.001],bottom:[0,-4.2,.001],default:[-1.8,2.35,3.2],inside:[2.8,2.4,-3.5]};
function view(name='default'){const p=viewVectors[name];controls.target.set(0,.6,0);camera.position.copy(controls.target).add(new THREE.Vector3(...p).multiplyScalar(1+targetExplode*1.15));camera.up.set(0,1,0);controls.update();}
view();
const outerIds=['01_','02_','03_','04_','14_'];
function offset(id){
 if(id.startsWith('01_'))return [0,.015,.07];if(id.startsWith('02_'))return [0,.025,-.07];if(id.startsWith('03_'))return [0,-.055,0];if(id.startsWith('04_'))return [0,.07,-.135];if(id.startsWith('14_'))return [.015,-.105,0];
 if(id.startsWith('10_'))return [0,.065,.095];if(id.startsWith('11_'))return [0,-.01,.12];if(id.startsWith('12_')||id==='OV5640_visual_only')return [.045,.02,.12];
 if(['05_','06_','07_','08_','25_'].some(s=>id.startsWith(s)))return [-.05,0,.12+(id.startsWith('06_')?.025:0)];
 if(id.startsWith('18_')||id==='Paper roll')return [0,.10,-.025];if(id.startsWith('19_'))return [.05,.10,-.025];
 if(id.startsWith('17_')||id==='Controller'||id==='Controller_connector_envelope')return [-.065,-.01,0];if(id==='Battery')return [.06,-.04,0];if(id==='Buck')return [.08,.01,0];
 if(id.startsWith('20_')||id.startsWith('21_')||id.startsWith('26_')||id==='ESP32'||id==='ESP32_connector_envelope')return [.03,.055,.025];if(id==='MY628'||id.startsWith('15_')||id.startsWith('16_')||id==='FPC_route_reference')return [0,-.015,.035];return [0,.03,.06];
}
function visibility(){parts.forEach(p=>{let visible=true;const id=p.userData.part_id||p.name;p.traverse(o=>{if(o.isMesh){o.castShadow=mode!=='inside';o.receiveShadow=mode!=='inside';}});
 if(p.userData.role==='reference')visible=$('#hardware').checked;
 if(outerIds.some(s=>id.startsWith(s))&&!$('#shell').checked)visible=false;
 p.traverse(o=>{if(!o.isMesh||!o.userData.shellMaterial)return;const m=o.userData.shellMaterial,ghost=mode==='inside';m.transparent=ghost;m.opacity=ghost?.12:1;m.depthWrite=!ghost;m.needsUpdate=true;o.castShadow=!ghost;o.receiveShadow=!ghost;});
 if(id==='OV5640_visual_only')visible=false;
 p.visible=visible;});}
function setMode(m){if(ritual?.busy)return;ritual?.hidePaper();mode=m;document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.mode===m));$('#shell').checked=true;$('#hardware').checked=m!=='exterior';targetExplode=m==='explode'?1:0;$('#explode').value=targetExplode*100;$('#explodeValue').textContent=`${Math.round(targetExplode*100)}%`;visibility();view(m==='inside'?'inside':'default');$('#status').textContent={exterior:'完整组装 · 自由观察',inside:'后壳半透明 · 查看内部连接',explode:'结构分解 · 非真实拆装路径'}[m];}
function prepareShell(p){const id=p.userData.part_id;if(!['02_Rear_housing','04_Paper_hatch'].includes(id))return;p.traverse(o=>{if(!o.isMesh)return;const shell=o.material.clone();o.userData.shellMaterial=shell;o.material=shell;if(id!=='02_Rear_housing')return;
 const g=o.geometry.clone(),pos=g.attributes.position,ix=g.index;const shellIndices=[],supportIndices=[];const n=ix?ix.count:pos.count;
 for(let i=0;i<n;i+=3){const ids=[0,1,2].map(k=>ix?ix.getX(i+k):i+k);let x=0,y=0,z=0;ids.forEach(j=>{x+=pos.getX(j)/3;y+=pos.getY(j)/3;z+=pos.getZ(j)/3;});const support=Math.abs(x)>.032&&Math.abs(x)<.071&&y>.044&&y<.066&&z>-.0175&&z<.001;(support?supportIndices:shellIndices).push(...ids);}
 g.setIndex(shellIndices.concat(supportIndices));g.clearGroups();g.addGroup(0,shellIndices.length,0);g.addGroup(shellIndices.length,supportIndices.length,1);o.geometry=g;o.material=[shell,shell.clone()];o.userData.supportTriangles=supportIndices.length/3;
 });}
function ready(gltf){model=gltf.scene;model.scale.setScalar(10);scene.add(model);model.traverse(o=>{if(o.userData.part_id){parts.push(o);o.userData.base=o.position.clone();o.userData.delta=new THREE.Vector3(...offset(o.userData.part_id));}if(o.isMesh){o.castShadow=true;o.receiveShadow=true;}});parts.forEach(prepareShell);visibility();$('#loading').hidden=true;$('#partCount').textContent=`${parts.filter(p=>p.userData.role==='print_part').length} 个结构零件 · V33 顶部嵌屏`;$('#status').textContent='完整组装 · 自由观察';ritual=createRitual({scene,model,parts,camera,controls,renderer,setMode,reduced,onStart:()=>{targetExplode=0;explode=0;}});window.__viewerReady=true;window.__viewer={scene,model,parts,camera,controls,renderer,setMode,ritual};}
const draco=new DRACOLoader();draco.setDecoderPath('./draco/');draco.setDecoderConfig({type:'wasm'});
let bytes;setTimeout(async()=>{try{const response=await fetch('./DASHAN_V33.glb');if(!response.ok)throw new Error(`模型下载失败：${response.status}`);bytes=new Uint8Array(await response.arrayBuffer());new GLTFLoader().setDRACOLoader(draco).parse(bytes.buffer,'',ready,e=>fail(e));}catch(e){fail(e);}},60);
function fail(e){console.error(e);$('#loading').innerHTML='<strong>相机暂时没有加载出来</strong><p>请刷新页面重试，你仍可以向下阅读项目与示例案卷。</p>';}
document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>model&&setMode(b.dataset.mode));document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>view(b.dataset.view));
$('#explode').oninput=e=>{const before=1+targetExplode*1.15;targetExplode=+e.target.value/100;const v=camera.position.clone().sub(controls.target).multiplyScalar((1+targetExplode*1.15)/before);camera.position.copy(controls.target).add(v);$('#explodeValue').textContent=`${e.target.value}%`;};
$('#shell').onchange=visibility;$('#hardware').onchange=visibility;$('#reset').onclick=()=>{if(model)setMode('exterior');$('#rotate').checked=false;controls.autoRotate=false;view();};
function zoom(f){const v=camera.position.clone().sub(controls.target);v.setLength(THREE.MathUtils.clamp(v.length()*f,controls.minDistance,controls.maxDistance));camera.position.copy(controls.target).add(v);controls.update();}
$('#zoomIn').onclick=()=>zoom(.8);$('#zoomOut').onclick=()=>zoom(1.25);
$('#rotate').onchange=e=>{controls.autoRotate=e.target.checked;};controls.addEventListener('start',()=>{controls.autoRotate=false;$('#rotate').checked=false;});
$('#studio').onchange=e=>{const dark=e.target.value==='dark';scene.background.set(dark?'#33383a':'#f5f5f2');renderer.toneMappingExposure=dark?1.05:.95;$('.hint').style.color=dark?'#c7ccc8':'';};
function size(){const r=rootEl.getBoundingClientRect();renderer.setSize(r.width,r.height);camera.aspect=r.width/r.height;camera.updateProjectionMatrix();}new ResizeObserver(size).observe(rootEl);size();
renderer.domElement.addEventListener('webglcontextlost',e=>{e.preventDefault();$('#status').textContent='图形资源已中断，请刷新页面恢复。';});
let last=0;function frame(t){requestAnimationFrame(frame);if(document.hidden){last=t;return;}const dt=Math.min((t-last)/1000,.1);last=t;explode=reduced?targetExplode:THREE.MathUtils.damp(explode,targetExplode,8,dt);parts.forEach(p=>p.position.copy(p.userData.base).addScaledVector(p.userData.delta,explode));ritual?.update(dt);controls.update();floor.visible=camera.position.y>0&&explode<.03&&!ritual?.paper.visible;renderer.render(scene,camera);}requestAnimationFrame(frame);
