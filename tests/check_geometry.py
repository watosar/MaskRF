"""Focused checks of coordinate convention and rejection of invalid mask data."""
from pathlib import Path
import tempfile
import numpy as np
from rf_repro.geometry import load_mask,boxes
Path('tmp/geometry-checks').mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(dir='tmp/geometry-checks') as tmp:
 p=Path(tmp)/'mask.csv';np.savetxt(p,[[1,0,0],[0,0,1]],fmt='%d',delimiter=',')
 c=dict(geometry=dict(kind='mask',file=str(p),pitch_mm=.2),substrate=dict(thickness_mm=.1),metal=dict(thickness_mm=.035))
 b=boxes(c)
 assert np.allclose(b[0][0],[-.3,0,.1]) and np.allclose(b[0][1],[-.1,.2,.135])
 assert np.allclose(b[1][0],[.1,-.2,.1])
 assert load_mask(p).sum()==2
 p.write_text('0,0.5\n1,0\n')
 try:load_mask(p)
 except ValueError:pass
 else:raise AssertionError('nonbinary CSV accepted')
print('PASS: asymmetric mask coordinates, dimensions, preservation, nonbinary rejection')
