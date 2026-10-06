import ctypes, math, os, random, struct, subprocess
from pathlib import Path
lib=ctypes.CDLL(str(Path('build/libframe_sv_test.so').resolve()))
fn=lib.frame_color_prepare
fn.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_float,ctypes.c_float,ctypes.c_float,ctypes.c_int]
fn.restype=ctypes.c_int
pack=lib.frame_color_pack;pack.argtypes=[ctypes.c_float]*3;pack.restype=ctypes.c_uint64
unpack=lib.frame_color_unpack;unpack.argtypes=[ctypes.c_uint64]+[ctypes.POINTER(ctypes.c_float)]*3
parser=lib.frame_color_test_parse;parser.argtypes=[ctypes.c_char_p,ctypes.POINTER(ctypes.c_uint64)]
for text in [b'{}',b'{"temperature":-1,"brightness":1.5,"saturation":2}',b'{"temperature":0.5}']:
 assert parser(text,ctypes.byref(ctypes.c_uint64()))
for text in [b'{"temperature":2}',b'{"temperature":NaN}',b'{"temperature":.5}',b'{"temperature":0,"temperature":1}',b'{"saturation":2.1}',b'{"hue":0}',b'{"brightness":0}',b'{"temperature":0}trailing']:
 assert not parser(text,ctypes.byref(ctypes.c_uint64()))
rng=random.Random(20261006);offsets=[304,464,480,496,512]
for i in range(1000):
 data=bytearray(rng.randbytes(528))
 for offset in offsets:struct.pack_into('<3f',data,offset,*[rng.uniform(0,3) for _ in range(3)])
 src=ctypes.create_string_buffer(bytes(data));dst=ctypes.create_string_buffer(528)
 s,v,t=rng.uniform(0,2),rng.uniform(.25,1.5),rng.uniform(-1,1)
 values=[ctypes.c_float() for _ in range(3)];unpack(pack(s,v,t),*[ctypes.byref(x) for x in values])
 assert all(abs(a-b.value)<.000051 for a,b in zip([s,v,t],values))
 assert fn(dst,src,1,1,0,0)==1 and dst.raw[:528]==data
 for ready in [0,1]:
  assert fn(dst,src,s,v,t,ready)==1 and src.raw[:528]==data
  touched={offset+j for offset in offsets for j in range(12)}|({476,477,478,479} if ready else set())
  assert all(a==b for j,(a,b) in enumerate(zip(data,dst.raw)) if j not in touched)
  gains=[v*(1+.35*t if t<0 else 1),v*(1-.08*abs(t)),v*(1-.35*t if t>0 else 1)]
  for offset in offsets:
   expected=[a*b for a,b in zip(struct.unpack_from('<3f',data,offset),gains)]
   assert all(abs(a-b)<2e-6 for a,b in zip(expected,struct.unpack_from('<3f',dst.raw,offset)))
  if ready:assert abs(struct.unpack_from('<f',dst.raw,476)[0]-s)<1e-6
 for invalid in [(math.nan,v,t),(s,math.inf,t),(s,v,2),(-1,v,t),(s,.1,t)]:
  sentinel=dst.raw;assert fn(dst,src,*invalid,1)==0 and dst.raw==sentinel
patch=lib.frame_color_patch
patch.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_uint)];patch.restype=ctypes.c_void_p
libc=ctypes.CDLL(None);libc.free.argtypes=[ctypes.c_void_p]
assert not patch(ctypes.create_string_buffer(b'x'*528),528,ctypes.byref(ctypes.c_size_t()),ctypes.byref(ctypes.c_uint()))
class Info(ctypes.Structure):
 _fields_=[('type',ctypes.c_uint32),('next',ctypes.c_void_p),('flags',ctypes.c_uint32),('size',ctypes.c_size_t),('code',ctypes.c_void_p)]
mock=ctypes.CDLL(str(Path('build/libvulkan_mock.so').resolve()))
mock.mock_shader_size.restype=ctypes.c_size_t
lib.dlsym.argtypes=[ctypes.c_void_p,ctypes.c_char_p];lib.dlsym.restype=ctypes.c_void_p
lib.frame_color_shader_enable()
lookup=ctypes.CFUNCTYPE(ctypes.c_void_p,ctypes.c_void_p,ctypes.c_char_p)
instance=lookup(lib.dlsym(mock._handle,b'vkGetInstanceProcAddr'))
device=lookup(instance(None,b'vkGetDeviceProcAddr'))
create=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.POINTER(Info),ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint64))(device(None,b'vkCreateShaderModule'))
assert not device(None,b'unknownSymbol')
raw=ctypes.create_string_buffer(b'x'*528);module=ctypes.c_uint64()
assert create(None,ctypes.byref(Info(15,None,0,528,ctypes.addressof(raw))),None,ctypes.byref(module))==0
assert mock.mock_shader_size()==528 and module.value==42 and lib.frame_color_shader_mask()==0
shader_dir=os.getenv('FRAME_COLOR_SHADER_DIR')
if shader_dir:
 for name,kind in [('tracked_camera_reprojection_simplified_rgb_nv12_ps.spv',1),('tracked_camera_reprojection_simplified_sharpen_rgb_nv12_ps.spv',2)]:
  data=Path(shader_dir,name).read_bytes();size=ctypes.c_size_t();profile=ctypes.c_uint()
  pointer=patch(ctypes.create_string_buffer(data),len(data),ctypes.byref(size),ctypes.byref(profile));assert pointer and profile.value==kind
  out=Path('build',name);out.write_bytes(ctypes.string_at(pointer,size.value));libc.free(pointer)
  subprocess.run([os.getenv('SPIRV_VAL','spirv-val'),str(out)],check=True)
  source=ctypes.create_string_buffer(data);info=Info(15,None,0,len(data),ctypes.addressof(source))
  before=lib.frame_color_shader_mask();mock.mock_shader_failure(-2)
  assert create(None,ctypes.byref(info),None,ctypes.byref(module))==-2 and lib.frame_color_shader_mask()==before
  mock.mock_shader_failure(0)
  assert create(None,ctypes.byref(info),None,ctypes.byref(module))==0
  assert mock.mock_shader_size()==size.value and lib.frame_color_shader_mask()&kind and source.raw[:len(data)]==data
  # Generator/debug metadata changes must not require a plugin update.
  metadata=bytearray(data);struct.pack_into('<I',metadata,8,0x12345678)
  name_words=[(4<<16)|5,struct.unpack_from('<I',data,12)[0]-1,0x74657374,0]
  at=20
  while struct.unpack_from('<I',metadata,at)[0]&65535!=71:at+=(struct.unpack_from('<I',metadata,at)[0]>>16)*4
  metadata=metadata[:at]+struct.pack('<4I',*name_words)+metadata[at:]
  pointer=patch(ctypes.create_string_buffer(bytes(metadata)),len(metadata),ctypes.byref(size),ctypes.byref(profile));assert pointer
  out.write_bytes(ctypes.string_at(pointer,size.value));libc.free(pointer)
  subprocess.run([os.getenv('SPIRV_VAL','spirv-val'),str(out)],check=True)
  optimizer=Path(os.getenv('SPIRV_VAL','spirv-val')).with_name('spirv-opt')
  if optimizer.exists():
   compact=Path('build','compact.spv');subprocess.run([str(optimizer),'--compact-ids',str(Path(shader_dir,name)),'-o',str(compact)],check=True)
   renumbered=compact.read_bytes();pointer=patch(ctypes.create_string_buffer(renumbered),len(renumbered),ctypes.byref(size),ctypes.byref(profile));assert pointer,'ID renumbering was rejected'
   out.write_bytes(ctypes.string_at(pointer,size.value));libc.free(pointer);subprocess.run([os.getenv('SPIRV_VAL','spirv-val'),str(out)],check=True)
  mutated=bytearray(data);mutated[-1]^=1
  assert not patch(ctypes.create_string_buffer(bytes(mutated)),len(data),ctypes.byref(size),ctypes.byref(profile))
print('PASS: 1000 color uniform snapshots, neutral identity, source/alpha preservation, invalid input and shader fingerprint guards')
