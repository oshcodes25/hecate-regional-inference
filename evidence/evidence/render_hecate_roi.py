"""Reproducible, offline E079 viewer and scientific summary figure."""
import base64
import html
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/hecate-roi'


def encode(a):
    return {'shape':list(a.shape),'bytes':base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()}


def render():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    result=json.loads((RUN/'result.json').read_text());rows=result['cases']
    payload=[]
    for row in rows:
        case=row['case'];x0,y0,x1,y1=case['roi_xyxy']
        a={k:np.load(ROOT/f['path'],allow_pickle=False) for k,f in row['outputs'].items()}
        parent=a['full'][...,y0:y1,x0:x1]
        ct=np.load(ROOT/case['input']['path'],allow_pickle=False)
        if case['sampling_um']==9.6:
            z,h,w=ct.shape;ct=np.rint(ct.reshape(z//4,4,h//4,4,w//4,4).mean(axis=(1,3,5))).astype(np.uint8)
        ct=ct[:,y0:y1,x0:x1]
        if not case['three_d']:
            parent=parent[None];a['roi']=a['roi'][None];a['naive']=a['naive'][None]
        payload.append({'label':f"{case['sample']} · {case['sampling_um']} µm · {'3D' if case['three_d'] else '2D'} · {'reverse' if case['reverse'] else 'forward'}",
            'case':case['index'],'spacing':case['sampling_um'],'batch':case['batch_size'],'roi':case['roi_xyxy'],
            'evaluated_z':row['measurements']['roi']['detail']['evaluated_z_interval'],
            'parent':encode(parent),'naive':encode(a['naive']),'regional':encode(a['roi']),'ct':encode(ct),
            'speed':row['full_over_roi_seconds'],'naive_fraction':row['naive_difference']['fraction_different'],
            'regional_difference':row['regional_difference']['differing_values'],
            'naive_mean_error':row['naive_difference']['mean_absolute_code_error']/255,
            'full_tiles':row['measurements']['full']['neural_tiles'],'roi_tiles':row['measurements']['roi']['neural_tiles'],
            'accumulator_reduction':row['temporary_accumulator_reduction']})
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'savefig.facecolor':'white'})
    fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
    labels=[f"{r['case']['sample'].replace('PHerc','')} {r['case']['sampling_um']}µm {'3D' if r['case']['three_d'] else '2D'}" for r in rows]
    y=np.arange(len(rows))
    axes[0].barh(y,[100*r['naive_difference']['fraction_different'] for r in rows],color='#be6943',label='Crop input first')
    axes[0].scatter([0]*len(rows),y,color='#136c67',label='Preserve full grid',zorder=3,s=24)
    axes[0].set_yticks(y,labels);axes[0].invert_yaxis();axes[0].set_xlabel('Saved values different from full-field reference (%)')
    axes[0].set_title('Correctness: every value checked');axes[0].legend(loc='lower right',fontsize=8)
    axes[1].barh(y,[r['full_over_roi_seconds'] for r in rows],color='#136c67')
    axes[1].set_yticks(y,labels);axes[1].invert_yaxis();axes[1].axvline(1,color='#555',linestyle='--')
    axes[1].set_xlabel('Full-field time / regional time');axes[1].set_title('Measured CPU time · one run per case')
    for ax in axes:ax.spines[['top','right']].set_visible(False)
    fig.suptitle('Hecate regional inference: preserve context while reducing work',fontsize=14)
    fig.savefig(RUN/'comparison.png',dpi=160,metadata={'Software':'Matplotlib'});plt.close(fig)
    from matplotlib.patches import Rectangle
    fig,axes=plt.subplots(1,2,figsize=(10,4.7),layout='constrained')
    for ax,row in zip(axes,rows[:2]):
        case=row['case'];ct=np.load(ROOT/case['input']['path'],mmap_mode='r',allow_pickle=False)
        pitch=case['sampling_um'];h,w=ct.shape[-2:]
        ax.imshow(ct[ct.shape[0]//2],cmap='gray',vmin=0,vmax=255,extent=(0,w*pitch,h*pitch,0))
        for group in row['measurements']['roi']['detail']['groups']:
            for y,x in group['origins']:
                ax.add_patch(Rectangle((x*pitch,y*pitch),256*pitch,256*pitch,fill=False,edgecolor='#4dd3ed',linewidth=1.2))
        x0,y0,x1,y1=case['roi_xyxy']
        ax.add_patch(Rectangle((x0*pitch,y0*pitch),(x1-x0)*pitch,(y1-y0)*pitch,fill=False,edgecolor='#ffac3d',linewidth=2.2))
        ax.set_title(case['sample']+' · actual central CT slice');ax.set_xlabel('Source-field x (µm)');ax.set_ylabel('Source-field y (µm)')
    fig.suptitle('Orange: requested output · Blue: four overlapping input tiles retained',fontsize=13)
    fig.savefig(RUN/'context.png',dpi=160,metadata={'Software':'Matplotlib'});plt.close(fig)
    table=''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in (
        p['label'],p['regional_difference'],f"{100*p['naive_fraction']:.2f}%",f"{p['naive_mean_error']:.4f}",f"{p['roi_tiles']}/{p['full_tiles']}",
        f"{p['speed']:.2f}×",f"{p['accumulator_reduction']:.1f}×"))+'</tr>' for p in payload)
    summary=f"The registered real-data checks {'passed' if result['all_gates_passed'] else 'failed'}. The primary two-case geometric-mean CPU speedup was {result['primary_geometric_mean_speedup']:.2f}×."
    document='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Hecate: reliable regional inference</title>
<style>:root{color-scheme:light;--green:#136c67;--ink:#213238}*{box-sizing:border-box}[hidden]{display:none!important}body{margin:0;background:#f5f4ef;color:var(--ink);font:16px/1.6 system-ui,sans-serif}main{max-width:1180px;margin:auto;padding:36px 24px 60px}h1{font-size:clamp(30px,5vw,48px);line-height:1.13;max-width:850px}h2{font-size:23px;margin:32px 0 10px}p{max-width:900px}.eyebrow{letter-spacing:.08em;text-transform:uppercase;color:var(--green);font-size:12px;font-weight:700}.lede{font-size:20px}.card{background:white;border:1px solid #d9dfda;border-radius:12px;padding:20px;margin:18px 0}.note{font-size:14px;color:#4a5b60}.controls{display:flex;gap:18px;flex-wrap:wrap;align-items:center}label{max-width:100%;min-width:0;display:flex;gap:8px;align-items:center;flex-wrap:wrap}select{max-width:100%;padding:9px;font-size:15px}input{max-width:100%}.panels{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin-top:20px}figure{margin:0;min-width:0}canvas{display:block;width:100%;aspect-ratio:1;image-rendering:pixelated;background:#000;border-radius:6px}figcaption{font-size:13px;margin-top:7px}a{color:var(--green)}.scroll{overflow:auto;max-width:100%}table{border-collapse:collapse;font-size:13px;width:100%;min-width:850px}td,th{text-align:left;padding:10px;border-bottom:1px solid #ddd;white-space:nowrap}th{white-space:normal;min-width:85px}td:first-child{white-space:normal;min-width:170px}img{width:100%;height:auto}.metrics{font-weight:650;font-size:15px}code{overflow-wrap:anywhere}details{margin:16px 0}summary{cursor:pointer;font-weight:650}@media(max-width:700px){main{padding:22px 15px}.panels{grid-template-columns:repeat(2,minmax(0,1fr))}.card{padding:14px}.lede{font-size:18px}h1{font-size:32px}}</style>
<main><div class="eyebrow">Private Progress Prize submission draft · 26 October 2026</div>
<h1>Zoom into the scan without changing the prediction.</h1>
<p class="lede">A regional Hecate reader that retains the full field's scan context and overlap weights, while evaluating only the required tiles.</p>
<p>Cutting out a small input changes what the model sees. This implementation requests a small <em>output</em> region while preserving its original input tiles. The reference is the original Hecate software run over the entire supplied field.</p>
<div class="card"><strong>SUMMARY</strong><p class="note">This is a demonstrated software correctness and efficiency contribution. No new letters or improved ink recall are claimed. These two physical fields were exposed in earlier research; they are not untouched reading-validation regions.</p></div>
<img src="context.png" alt="Two actual CT fields showing the requested orange region and four larger blue input contexts retained"><p class="note">The orange square is the output requested. The blue boxes show the surrounding input retained to reproduce the larger analysis. These are small scan fields, not entire unrolled scrolls.</p>
<h2>Inspect the actual outputs</h2><p class="note">All panels share one display scale. White means a larger model score, not verified ink. CT brightness is measured scan intensity. The difference panel compares naïve input cropping with the full-field reference; corrected regional outputs are checked value by value.</p>
<div class="card"><div class="controls"><label>Case <select id="case" aria-label="Benchmark case"></select></label><label id="depth-control">Depth <input id="depth" type="range" min="0" max="63" value="32"><output id="depth-label"></output></label><label>Display ceiling <input id="ceiling" type="range" min="1" max="255" value="255"><output id="ceiling-label">255</output></label></div>
<p id="metrics" class="metrics"></p><div class="panels">
<figure><canvas id="ct"></canvas><figcaption>CT slice · raw intensity</figcaption></figure>
<figure><canvas id="parent"></canvas><figcaption>Full-field prediction, cropped</figcaption></figure>
<figure><canvas id="naive"></canvas><figcaption>Input cropped before reading</figcaption></figure>
<figure><canvas id="regional"></canvas><figcaption>Our regional prediction</figcaption></figure>
<figure><canvas id="difference"></canvas><figcaption>Absolute naïve-crop error</figcaption></figure>
</div><p id="geometry" class="note"></p><p class="note">The depth control moves through sampled CT planes, not successive sheets of the scroll. The display ceiling only changes visible contrast; it cannot alter predictions or reported counts. A 2D prediction has no output-depth slider and is shown beside the central CT slice.</p></div>
<h2>Every registered case</h2><div class="scroll"><table><thead><tr><th>Case</th><th>Corrected differences</th><th>Naïve values changed</th><th>Mean absolute score error</th><th>ROI/full neural tiles</th><th>Wall-time speedup</th><th>Smaller accumulators</th></tr></thead><tbody>TABLE</tbody></table></div><p class="note">Mean error is on the probability scale 0–1 and measures disagreement with the full-field output, not disagreement with true ink.</p>
<img src="comparison.png" alt="All eight comparisons of incorrect crop outputs and measured CPU speedups">
<h2>What is contributed</h2><p>The standalone API and CLI add region requests to the pinned Hecate runtime. The implementation keeps the full-array tile origins, forced end tiles, original batch groups, depth direction, column support, Hann weights and uint8 encoding. It reads full contexts through array slices and allocates blend accumulators only for the requested region. PNG/NPY outputs carry source-index metadata.</p>
<p>The global-grid principle has a clear predecessor: <a href="https://github.com/ScrollPrize/villa/pull/1247">villa PR #1247</a> for surface segmentation. Hecate's <a href="https://huggingface.co/scrollprize/hecate/discussions/1">shared-feature 2D/3D proposal</a> also predates this work and is not claimed here. The contribution is this Hecate implementation, its equivalence tests and measured resource savings.</p>
<details><summary>How the comparison was controlled</summary><p>Two existing real CT fields from PHerc9B and PHerc500P2; two resolutions; 2D and 3D output; forward/reverse depth and batch sizes 1/3. The original 2.4 µm inputs were already qualified; the coarse test inputs use a fixed 4×4×4 average and rounding. CPU float32 with four threads, fixed warmup, balanced run order, no changed weights or thresholds. One timed run per case; timings are local measurements, not a claim about GPU or remote-storage performance. All saved output values are independently compared.</p><p>The supplied parent fields are 512×512 and 472×472 pixels at 2.4 µm. They are not entire scrolls. The API requires the original full source array or lazy store: an already cropped file cannot recover omitted context. Exact equality is verified for the tested runtime, device and settings; CUDA/bfloat16 are not validated here.</p></details>
<details><summary>Limits and earlier negative results</summary><p>The full-field result is a software reference, not ground-truth ink. There is no inference about whole letters, newly discovered text, statistical independence of pixels or unseen-model generalization. Prior projection, learning, binary-union and output-precision experiments failed their practical gates; none are relabelled as successful. This submission addresses regional execution and resource use.</p></details>
<p class="note">Oisin McGlone · Code: MIT, with Vesuvius Challenge upstream attribution. CT data and derived scan visualizations: CC BY-NC 4.0, unless the source asset specifies otherwise. Dataset: Angelotti et al., <a href="https://scrollprize.org/data">Vesuvius Challenge — CT Scans of Herculaneum Papyri</a>. No external submission or publication has been made.</p>
</main><script>const DATA=PAYLOAD;
for(const item of DATA)for(const key of ['ct','parent','naive','regional']){const a=item[key];a.values=Uint8Array.from(atob(a.bytes),c=>c.charCodeAt(0));delete a.bytes;}
const select=document.getElementById('case'),depth=document.getElementById('depth'),ceiling=document.getElementById('ceiling');DATA.forEach((x,i)=>select.add(new Option(x.label,i)));
function frame(a,z){const n=a.shape[1]*a.shape[2];return a.values.subarray(z*n,(z+1)*n);}
function paint(id,a,z,limit,other){const c=document.getElementById(id);c.width=a.shape[2];c.height=a.shape[1];const ctx=c.getContext('2d'),im=ctx.createImageData(c.width,c.height),v=frame(a,z);for(let i=0;i<v.length;i++){const n=other?Math.abs(v[i]-other[i]):v[i],b=Math.min(255,Math.round(n*255/limit));im.data[4*i]=b;im.data[4*i+1]=b;im.data[4*i+2]=b;im.data[4*i+3]=255;}ctx.putImageData(im,0,0);}
function render(reset=false){const r=DATA[+select.value],n=r.parent.shape[0];if(reset){depth.max=n-1;depth.value=Math.floor(n/2);}const z=+depth.value,lim=+ceiling.value;document.getElementById('depth-control').hidden=n===1;document.getElementById('depth-label').textContent=`${z+1}/${n}`;document.getElementById('ceiling-label').textContent=lim;
paint('ct',r.ct,n===1?Math.floor(r.ct.shape[0]/2):z,255);for(const k of ['parent','naive','regional'])paint(k,r[k],z,lim);paint('difference',r.naive,z,lim,frame(r.parent,z));
document.getElementById('metrics').textContent=`${r.regional_difference} corrected values differ · ${(r.naive_fraction*100).toFixed(2)}% differ after naïve cropping (mean score error ${r.naive_mean_error.toFixed(3)}) · ${r.roi_tiles}/${r.full_tiles} neural tiles · ${r.speed.toFixed(2)}× measured speedup`;
document.getElementById('geometry').textContent=`ROI [${r.roi.join(', ')}] in source XY pixels; ${(r.parent.shape[2]*r.spacing).toFixed(1)} × ${(r.parent.shape[1]*r.spacing).toFixed(1)} µm. Each displayed pixel is ${r.spacing} µm. Batch size ${r.batch}. Values are uint8 codes 0–255; probability = code/255.`+(n>1&&(z<r.evaluated_z[0]||z>=r.evaluated_z[1])?' This edge plane was not evaluated by the model; its output is zero-filled.':'');}
select.addEventListener('change',()=>render(true));depth.addEventListener('input',()=>render());ceiling.addEventListener('input',()=>render());render(true);
</script></html>'''.replace('SUMMARY',html.escape(summary)).replace('TABLE',table).replace('PAYLOAD',json.dumps(payload,separators=(',',':')))
    (RUN/'REPORT.html').write_text(document)
    (RUN/'REPORT.txt').write_text(summary+'\n\n'+result['scope']+'\n\n'+result['validation_role']+'\n\n'+'\n'.join(
        f"{p['label']}: corrected differences={p['regional_difference']}; naïve changed={100*p['naive_fraction']:.3f}%; neural tiles={p['roi_tiles']}/{p['full_tiles']}; wall speedup={p['speed']:.3f}; temporary accumulator reduction={p['accumulator_reduction']:.1f}." for p in payload)+'\n')
    print('Rendered',RUN/'REPORT.html')


if __name__=='__main__':render()
