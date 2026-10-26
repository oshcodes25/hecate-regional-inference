import fs from 'node:fs/promises';
import path from 'node:path';
const out=process.argv[2];
const targets=await (await fetch('http://127.0.0.1:9233/json')).json();
const target=targets.find(t=>t.type==='page');
if(!target)throw new Error('No isolated QA page');
const ws=new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true});});
let id=0;const pending=new Map(),exceptions=[];
ws.addEventListener('message',event=>{const message=JSON.parse(event.data);if(message.id){const p=pending.get(message.id);if(p){pending.delete(message.id);clearTimeout(p.timer);message.error?p.reject(message.error):p.resolve(message.result);}}else if(message.method==='Runtime.exceptionThrown')exceptions.push(message.params);});
function call(method,params={}){return new Promise((resolve,reject)=>{const key=++id;const timer=setTimeout(()=>reject(new Error(method+' timeout')),15000);pending.set(key,{resolve,reject,timer});ws.send(JSON.stringify({id:key,method,params}));});}
async function evaluate(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
async function shot(name){const r=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await fs.writeFile(path.join(out,name),Buffer.from(r.data,'base64'));}
await call('Page.enable');await call('Runtime.enable');
await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1080,deviceScaleFactor:1,mobile:false});
await call('Page.navigate',{url:process.argv[3]||'http://127.0.0.1:8767/REPORT.html'});
for(let i=0;i<100;i++){if(await evaluate('document.readyState === "complete" && typeof DATA !== "undefined" && document.images.length === 2 && [...document.images].every(x=>x.complete&&x.naturalWidth>0)'))break;await new Promise(r=>setTimeout(r,50));}
const desktop=await evaluate(`({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,images:[...document.images].map(i=>({src:i.getAttribute('src'),decoded:i.naturalWidth>0})),caseCount:DATA.length})`);
const interactions=await evaluate(`(()=>{const checks=[];for(let i=0;i<DATA.length;i++){select.value=i;select.dispatchEvent(new Event('change'));const r=DATA[i],n=r.parent.shape[0];for(const z of [...new Set([0,Math.floor(n/2),n-1])])for(const cap of [255,32]){depth.value=z;ceiling.value=cap;depth.dispatchEvent(new Event('input'));ceiling.dispatchEvent(new Event('input'));const p=document.getElementById('parent'),q=document.getElementById('regional'),a=p.getContext('2d').getImageData(0,0,p.width,p.height).data,b=q.getContext('2d').getImageData(0,0,q.width,q.height).data;if(a.length!==b.length||!a.every((x,j)=>x===b[j]))throw Error('Displayed corrected image differs');checks.push({case:i,z,ceiling:cap,canvasMatch:true,depthControlHidden:getComputedStyle(document.getElementById('depth-control')).display==='none'});} }select.value=0;ceiling.value=255;select.dispatchEvent(new Event('change'));return checks;})()`);
await evaluate('scrollTo(0,0)');await shot('browser-desktop-top.png');
await evaluate("document.getElementById('case').scrollIntoView({block:'start'})");await shot('browser-desktop-viewer.png');
await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
await evaluate('scrollTo(0,0)');
const mobile=await evaluate('({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,tableScrolls:document.querySelector(".scroll").scrollWidth>document.querySelector(".scroll").clientWidth})');
await shot('browser-mobile-top.png');await evaluate("document.getElementById('case').scrollIntoView({block:'start'})");await shot('browser-mobile-viewer.png');
const result={status:'passed',desktop,mobile,interactiveChecks:interactions,exceptions};
if(desktop.width!==1440||desktop.scrollWidth>1440||mobile.width!==390||mobile.scrollWidth>390||exceptions.length||desktop.caseCount!==8||desktop.images.some(x=>!x.decoded))throw new Error('Layout/image/runtime check failed '+JSON.stringify(result));
await fs.writeFile(path.join(out,'browser-check.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({status:result.status,desktop,mobile,interactiveChecks:interactions.length,exceptions:exceptions.length}));ws.close();
