"""Reviewed operational continuation; preserves the interrupted attempt and all settings."""
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import sys
import hecate_repeatability as original
import resume_hecate_broad_projection as guard

ROOT=original.ROOT;PARENT=ROOT/'runs/hecate-repeatability';RUN=PARENT/'continuation-01'


def register():
    p=original.plan();state=original.read(PARENT/'execution.json');failure=original.read(PARENT/'failure.json')
    if state['completed']!=[0] or failure['case']!=1 or failure['seconds']>=600 or failure['exit_code']!=-15:
        raise ValueError('This continuation only covers the reviewed power interruption')
    if list((PARENT/'case-01').iterdir()):raise ValueError('Unexpected partial prediction requires separate review')
    observed=guard.power()
    if not(observed['AC'] is True and observed['lid_closed'] is False):raise ValueError('AC/open lid required')
    first=original.read(PARENT/'case-00/result.json')
    for row in first['rows']:
        if original.core.sha(PARENT/'case-00'/row['output'])!=row['output_sha256']:raise ValueError('Completed result changed')
    RUN.mkdir(exist_ok=False)
    shutil.copyfile(PARENT/'registered-plan.json',RUN/'registered-plan.json')
    shutil.copytree(PARENT/'case-00',RUN/'case-00')
    state['status']='ready_after_review';state['continuation_note']='Case 0 reused exactly; initial interrupted case 1 is preserved in parent. Remaining workers use unchanged settings.'
    original.core.save(RUN/'execution.json',state)
    amendment={'registered_at':datetime.now(timezone.utc).isoformat(),'original_plan':original.core.file_record(PARENT/'registered-plan.json'),
        'interrupted_execution':original.core.file_record(PARENT/'execution.json'),'failure':original.core.file_record(PARENT/'failure.json'),
        'review':'OS power log records AC to battery at 2026-10-26 17:36:29 AEDT, followed by clamshell sleep at 17:36:31. Guard terminated worker 1 after 45.809s, before the 600s cap. No prediction file or completed repeat was saved by that worker. Case 0 completed all three repetitions before interruption.',
        'unchanged':'Same input/checkpoint/source hashes, coordinates, methods, order, three repetitions, seed, threads, precision and per-worker limits. No outcome-based selection or parameter adjustment.',
        'reuse':'Only complete case 0, copied byte-for-byte and hash checked. Rerun the interrupted case 1 in a fresh directory, then fixed cases 2–4.',
        'consumed_worker_seconds':state['worker_seconds'],'remaining_worker_seconds':p['resources']['total_worker_seconds']-state['worker_seconds'],
        'resources':'Original 2400s aggregate cap includes both original attempts and this continuation. Each remaining worker retains its original cap. A further interruption is preserved and cannot automatically retry.',
        'power_at_registration':observed,'launcher':original.core.file_record(Path(__file__))}
    original.core.freeze(RUN/'amendment.json',amendment);print('Operational continuation registered')


def launch():
    amendment=original.read(RUN/'amendment.json');original.core.verify(amendment['launcher'])
    check=guard.power
    def logged_power():
        result=check()
        with (RUN/'power-observations.jsonl').open('a') as out:out.write(json.dumps({'time':datetime.now(timezone.utc).isoformat(),**result})+'\n')
        return result
    guard.power=logged_power;original.RUN=RUN;original.launch()


def summarize():
    original.RUN=RUN;original.summarize()


if __name__=='__main__':globals()[sys.argv[1]]()
