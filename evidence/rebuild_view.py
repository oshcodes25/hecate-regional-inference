"""Rebuild the saved visual report in a temporary folder and compare exact files.
Requires the recorded plotting environment; performs no model inference.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import tempfile
import numpy as np


def rebuild(package,DEST):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    payload=json.loads((package/'repeatability/view-data.json').read_text())
    summary=json.loads((package/'repeatability/result.json').read_text())
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'savefig.facecolor':'white'})
    labels=[r['label'].replace('PHerc','').replace(' · ',' ') for r in payload];y=np.arange(len(labels))
    fig,axes=plt.subplots(1,2,figsize=(12.5,6.7),layout='constrained')
    for ax,key,title,xlabel in [(axes[0],'full_over_regional','Compared with full-field inference','Full-field seconds / regional seconds'),(axes[1],'regional_over_halo','Compared with careful context cropping','Regional seconds / context-crop seconds')]:
        values=np.array([r['statistics'][key]['median'] for r in payload]);low=np.array([r['statistics'][key]['minimum'] for r in payload]);high=np.array([r['statistics'][key]['maximum'] for r in payload])
        ax.errorbar(values,y,xerr=[values-low,high-values],fmt='o',color='#176b58',capsize=3)
        ax.axvline(1,color='#777',linestyle='--',linewidth=1);ax.set_yticks(y,labels);ax.invert_yaxis();ax.set_xlabel(xlabel);ax.set_title(title);ax.spines[['top','right']].set_visible(False)
    fig.suptitle('Three local repeats per request · points = median, bars = observed min–max',fontsize=12)
    fig.savefig(DEST/'repeatability.png',dpi=160,metadata={'Software':'Matplotlib'});plt.close(fig)
    rows=[]
    for r in payload:
        s=r['statistics'];ratio=s['full_over_regional'];halo=s['regional_over_halo'];storage=s['halo_over_regional_accumulator']['median']
        rows.append('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in [r['label'],f"{ratio['median']:.2f}× ({ratio['minimum']:.2f}–{ratio['maximum']:.2f})",f"{halo['median']:.3f} ({halo['minimum']:.3f}–{halo['maximum']:.3f})",f'{storage:.2f}×'])+'</tr>')
    template=(package/'evidence/repeated/page-template.html').read_text()
    template=template.replace('__PAYLOAD__',json.dumps(payload,separators=(',',':'))).replace('__TABLE__',''.join(rows)).replace('__GATES__','All four registered gates passed.' if summary['all_gates_passed'] else 'Some registered gates failed; inspect the full results before claiming a benefit.')
    (DEST/'START_HERE.html').write_text(template)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args();package=args.package.resolve()
    with tempfile.TemporaryDirectory(prefix='hecate-rebuilt-view-') as directory:
        target=Path(directory);rebuild(package,target)
        for name in ['START_HERE.html','repeatability.png']:
            if (target/name).read_bytes()!=(package/name).read_bytes():raise ValueError('Rebuilt artifact differs: '+name)
            print('PASS:',name,hashlib.sha256((target/name).read_bytes()).hexdigest())
    print('Saved visual artifacts rebuilt exactly. No model was run.')


if __name__=='__main__':main()
