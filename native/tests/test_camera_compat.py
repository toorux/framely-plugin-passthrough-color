import ctypes,os,struct
from pathlib import Path
lib=ctypes.CDLL(str(Path('build/libframe_sv_test.so').resolve()))
probe=lib.frame_test_camera_shape;probe.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint]
path=os.getenv('FRAME_TEST_VRCLIENT')
if path:
 data=Path(path).read_bytes()
 for method,(offset,size) in enumerate([(0x1a8218,52),(0x1a8680,72),(0x1a8520,104),(0x1a8740,92)]):
  body=data[offset:offset+size]
  assert probe(ctypes.create_string_buffer(body),len(body),method)
  moved=bytearray(body)
  for i in range(0,len(body),4):
   w=struct.unpack_from('<I',body,i)[0]
   if w&0x7c000000==0x14000000:struct.pack_into('<I',moved,i,(w&0xfc000000)|123)
  assert probe(ctypes.create_string_buffer(bytes(moved)),len(moved),method),'external call relocation rejected'
  changed=bytearray(body);changed[4]^=1
  assert not probe(ctypes.create_string_buffer(bytes(changed)),len(changed),method),'changed ABI accepted'
  assert not probe(ctypes.create_string_buffer(body),len(body)-1,method)
 print('PASS: camera method offsets/call relocation independent; changed ABI and truncated code rejected')
else:print('SKIP camera sample: set FRAME_TEST_VRCLIENT to a read-only vrclient copy')
