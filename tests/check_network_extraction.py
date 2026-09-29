import numpy as np
# Known reciprocal lossless two-port, with nonzero incident wave at the other port.
theta=.7
S=np.array([[1j*np.sin(theta),np.cos(theta)],[np.cos(theta),1j*np.sin(theta)]])
A=np.array([[1,.15j],[.2,1]],complex);B=S@A
np.testing.assert_allclose(B@np.linalg.inv(A),S,atol=1e-14)
assert np.max(abs(B[:,0]/A[0,0]-S[:,0]))>.1
np.testing.assert_allclose(np.linalg.svd(S,compute_uv=False),[1,1],atol=1e-14)
print('PASS: incident-wave matrix inversion, reciprocal lossless reference')
