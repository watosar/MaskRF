import argparse, copy, hashlib, json, os, re, signal, shutil, subprocess, sys, time
from pathlib import Path
import numpy as np
import yaml
from .geometry import boxes,mask_audit,load_mask
from .model import build
from .postprocess import process,db


def dump(path,value):Path(path).write_text(json.dumps(value,indent=2))


def config(path):
    path=Path(path).resolve(); c=yaml.safe_load(path.read_text())
    if c['geometry']['kind']=='mask':
        c['geometry']['file']=str((path.parent/c['geometry']['file']).resolve())
    if c['boundary'][4]!='PEC':raise ValueError('This implementation requires the z=0 PEC ground plane')
    if len(c['boundary'])!=6 or c['frequency_GHz'][2]<2:raise ValueError('Invalid boundary/frequency configuration')
    for item in ['pitch_mm'] if c['geometry']['kind']=='mask' else []:
        if c['geometry'][item]<=0:raise ValueError(item)
    return c


def inspect(c,out):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    fdtd,cs,ports,mesh=build(c)
    cs.Write2XML(str(out/'geometry.xml'));dump(out/'mesh.json',mesh);dump(out/'geometry-audit.json',mask_audit(c))
    fig,ax=plt.subplots(2,1,figsize=(10,6),gridspec_kw={'height_ratios':[3,1]})
    g=c['geometry'];p=c['ports'];h=c['substrate']['thickness_mm'];t=c['metal']['thickness_mm']
    half=load_mask(g['file']).shape[1]*g['pitch_mm']/2 if g['kind']=='mask' else 0
    length=half+p['feed_length_mm'];ymin,ymax=c['domain']['y_mm']
    ax[0].add_patch(Rectangle((-length,ymin),2*length,ymax-ymin,facecolor='#d6ead3',label='substrate / ground beneath'))
    for start,stop in boxes(c):ax[0].add_patch(Rectangle(start[:2],stop[0]-start[0],stop[1]-start[1],color='#555555'))
    for i,sign in enumerate([-1,1]):
        y=p['y_mm'][i];begin=-length if sign==-1 else half
        ax[0].add_patch(Rectangle((begin,y-p['width_mm']/2),p['feed_length_mm'],p['width_mm'],color='#555555'))
        plane=sign*(length-p['measurement_shift_mm'])
        ax[0].plot([plane,plane],[y-.4,y+.4],color='red');ax[0].text(plane,y+.5,f'P{i+1} reference',fontsize=8)
    for via in g.get('shorts',[]):ax[0].plot(*via['xy_mm'],'bs',ms=4)
    ax[0].set_xlim(-length,length);ax[0].set_ylim(ymin,ymax);ax[0].set_aspect('equal');ax[0].set_ylabel('y (mm)');ax[0].set_xlabel('x (mm)')
    ax[0].set_title(c['name']+'; PEC preliminary model')
    ax[1].add_patch(Rectangle((-length,0),2*length,h,color='#d6ead3'))
    ax[1].plot([-length,length],[0,0],'k-',label='PEC GND z=0');ax[1].plot([-length,length],[h+t,h+t],color='#555555',label='top metal upper surface')
    ax[1].set_xlim(-length,length);ax[1].set_ylim(-h,h*3);ax[1].set_ylabel('z (mm)');ax[1].legend(fontsize=8)
    fig.tight_layout();fig.savefig(out/'geometry.png');plt.close(fig)
    return mesh


def run(c,out,source=None):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    if source:(out/'original.yaml').write_text(Path(source).read_text())
    # Snapshot mask and use that snapshot for all later processing.
    if c['geometry']['kind']=='mask':
        c=copy.deepcopy(c);a=load_mask(c['geometry']['file']);np.savetxt(out/'mask.csv',a,delimiter=',',fmt='%d');c['geometry']['file']=str(out/'mask.csv')
    dump(out/'effective.json',c)
    shutil.copytree(Path(__file__).parent,out/'source_snapshot',ignore=shutil.ignore_patterns('__pycache__'))
    inspect(c,out)
    status=[]
    for ex in c['solver']['excitations']:
        start=time.monotonic()
        cmd=['uv','run','--no-project','--python',sys.executable,'-m','rf_repro','worker','--run',str(out),'--excitation',str(ex)]
        resource=out/f'resources-{ex}.txt'
        if Path('/usr/bin/time').exists():cmd=['/usr/bin/time','-v','-o',str(resource)]+cmd
        with (out/f'solver-{ex}.log').open('w') as log:
            proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:code=proc.wait(timeout=c['solver']['timeout_s'])
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
                code=124
        txt=(out/f'solver-{ex}.log').read_text();steps=re.findall(r'Number of timesteps:\s*(\d+)',txt)
        # v0.0.36 emits a warning on energy criterion failure; require normal finish as well.
        finished=bool(re.search(r'Time for \d+ iterations with [\d.]+ cells',txt))
        failed_decay='before the end-criteria' in txt.lower()
        status.append(dict(excitation=ex,command=cmd,exit_code=code,wall_seconds=time.monotonic()-start,
                           normal_finish=finished,decay_confirmed=code==0 and finished and not failed_decay,
                           caution='Inspect solver log; energy criterion is independent of mesh convergence'))
        dump(out/'status.json',status)
        if code:raise RuntimeError(f'Solver failed ({code}); see {out}/solver-{ex}.log')
    process(out)
    return out


def compare_runs(paths,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    import matplotlib.pyplot as plt
    results=[];fig,ax=plt.subplots()
    prev=None
    for p in paths:
        f,s,m=process(p);ax.plot(f/1e9,db(s['s21']),label=Path(p).name)
        c=json.loads((Path(p)/'effective.json').read_text());pb=c['validation']['passband_GHz'];use=(f>=pb[0]*1e9)&(f<=pb[1]*1e9)
        row=dict(run=str(p),metrics=m,time_decay_confirmed=all(e['decay_confirmed'] for e in json.loads((Path(p)/'status.json').read_text())))
        if prev:
            pf,ps,pm=prev
            if not np.array_equal(f,pf):raise ValueError('Frequency grids differ')
            row['max_complex_delta']=max(float(np.max(abs(s[k]-ps[k]))) for k in s)
            row['passband_s21_max_delta_dB']=float(np.max(abs(db(s['s21'])[use]-db(ps['s21'])[use])))
            a=m['first_downward_3dB_GHz'];b=pm['first_downward_3dB_GHz']
            row['feature_relative_change']=None if a is None or b is None else abs(a-b)/a
            row['numerical_threshold_pass']=bool(row['passband_s21_max_delta_dB']<=.2 and
              (row['feature_relative_change']<=.01 if row['feature_relative_change'] is not None else row['max_complex_delta']<=.02))
            # Keep the historical amplitude/feature flag for archived reports,
            # but never use it as a claim of full complex-matrix convergence.
            row['amplitude_feature_threshold_pass']=row['numerical_threshold_pass']
            row['complex_delta_tolerance']=c['validation'].get('complex_delta_tolerance',.02)
            row['full_s_threshold_pass']=bool(row['amplitude_feature_threshold_pass'] and
                row['max_complex_delta']<=row['complex_delta_tolerance'])
            row['coherent_power_tolerance']=1.02
            row['coherent_passivity_threshold_pass']=bool(m['max_singular_value']**2<=1.02)
        results.append(row);prev=(f,s,m)
    ax.set(xlabel='Frequency (GHz)',ylabel='S21 (dB)',ylim=(-50,2));ax.legend();ax.grid();fig.tight_layout();fig.savefig(out/'comparison.png');plt.close(fig)
    dump(out/'comparison.json',results)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['inspect','run','postprocess','convergence','worker','compare','evaluate'])
    parser.add_argument('--config');parser.add_argument('--out');parser.add_argument('--run');parser.add_argument('--excitation',type=int);parser.add_argument('--runs',nargs='+')
    parser.add_argument('--mask');parser.add_argument('--reuse-run')
    a=parser.parse_args()
    if a.command=='evaluate':
        if not a.mask or not a.out:parser.error('evaluate requires --mask and --out')
        from .api import evaluate_mask
        try:
            result=evaluate_mask(a.mask,a.out,config_path=a.config,reuse_run=a.reuse_run)
            print(json.dumps(result.to_dict(),allow_nan=False))
        except (ValueError,OSError,RuntimeError,KeyError,TypeError,yaml.YAMLError) as error:
            print(json.dumps({'status':'failed','error':str(error)}),file=sys.stderr)
            raise SystemExit(1)
        return
    if a.command=='worker':
        out=Path(a.run);c=json.loads((out/'effective.json').read_text());fdtd,_,_,_=build(c,a.excitation)
        fdtd.Run(str(out/f'excite-{a.excitation}'),cleanup=False,numThreads=c['solver']['threads'],verbose=1);return
    if a.command=='postprocess':process(a.run);return
    if a.command=='compare':compare_runs(a.runs,a.out);return
    c=config(a.config)
    if a.command=='inspect':
        m=inspect(c,a.out or 'tmp/rf-repro-inspect');print(json.dumps({k:v for k,v in m.items() if k!='lines_mm'},indent=2));return
    if a.command=='run':run(c,a.out,a.config);return
    if a.command=='convergence':
        root=Path(a.out);root.mkdir(parents=True,exist_ok=False);paths=[]
        for i,level in enumerate(c['convergence']):
            cc=copy.deepcopy(c);cc['mesh'].update(level)
            paths.append(run(cc,root/f'level-{i+1}',a.config))
        compare_runs(paths,root)

if __name__=='__main__':main()
