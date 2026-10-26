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
await call('Page.enable');await call('Runtime.enable');await call('Network.enable');
await call('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});
await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1080,deviceScaleFactor:1,mobile:false});
await call('Page.navigate',{url:process.argv[3]});
for(let i=0;i<100;i++){if(await evaluate('document.readyState === "complete" && typeof CASES !== "undefined" && document.getElementById("scan").width > 400'))break;await new Promise(r=>setTimeout(r,50));}
const desktop=await evaluate('({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,cases:CASES.length,title:document.title})');
const interactions=await evaluate(`(()=>{const checks=[];for(let i=0;i<CASES.length;i++){sample.value=i;sample.dispatchEvent(new Event('change'));for(const name of ['full','naive','regional'])for(const limit of [255,32]){document.querySelector('[data-mode="'+name+'"]').click();ceiling.value=limit;ceiling.dispatchEvent(new Event('input'));const r=CASES[i],source=name==='full'?r.reference:r[name];for(const id of ['reference','candidate','difference']){const a=document.getElementById(id).getContext('2d').getImageData(0,0,64,64).data;for(let j=0;j<4096;j++){const raw=id==='reference'?r.reference[j]:id==='candidate'?source[j]:Math.abs(source[j]-r.reference[j]);const target=Math.min(255,Math.round(raw*255/limit));if(a[j*4]!==target||a[j*4+1]!==target||a[j*4+2]!==target||a[j*4+3]!==255)throw new Error('Rendered data mismatch');}}if(document.querySelectorAll('[aria-pressed="true"]').length!==1)throw new Error('Step selection inaccessible');checks.push({sample:i,mode:name,ceiling:limit,all4096PixelsPerPanelChecked:true});}}sample.value=0;ceiling.value=255;document.querySelector('[data-mode="regional"]').click();return checks;})()`);
await evaluate('scrollTo(0,0)');await shot('review-desktop-top.png');
await evaluate('document.getElementById("demo-heading").scrollIntoView({block:"start"})');await shot('review-desktop-demo.png');
await evaluate('document.querySelector("[data-mode=naive]").click()');await shot('review-desktop-crop.png');
await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
await evaluate('document.querySelector("[data-mode=regional]").click();scrollTo(0,0)');
const mobile=await evaluate('({width:innerWidth,scrollWidth:document.documentElement.scrollWidth})');await shot('review-mobile-top.png');
await evaluate('document.getElementById("step-label").scrollIntoView({block:"start"})');await shot('review-mobile-output.png');
const result={status:'passed',offline:true,desktop,mobile,interactions,exceptions};
if(desktop.width!==1440||desktop.scrollWidth>1440||mobile.width!==390||mobile.scrollWidth>390||desktop.cases!==2||exceptions.length)throw new Error(JSON.stringify(result));
await fs.writeFile(path.join(out,'review-browser-check.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({status:result.status,offline:true,desktop,mobile,statesChecked:interactions.length,exceptions:exceptions.length}));ws.close();
