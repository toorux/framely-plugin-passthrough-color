import ctypes, json, math, random, struct
from pathlib import Path

lib = ctypes.CDLL(str(Path('build/libframe_sv_uniform.so').resolve()))
fn = lib.frame_sv_prepare
fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
               ctypes.c_float, ctypes.c_float]
fn.restype = ctypes.c_int
offsets = [304, 464, 480, 496, 512]
rng = random.Random(20261001)

def prepare(data, mono, saturation, brightness):
    src, dst = ctypes.create_string_buffer(data), ctypes.create_string_buffer(528)
    changed = fn(dst, src, mono, saturation, brightness)
    assert src.raw[:528] == data, 'source modified'
    return dst.raw[:528], changed

def colors(data):
    return [struct.unpack_from('<3f', data, offset) for offset in offsets]

def rendered_tint(cs, u, v, strength):
    weights = [(1-u)*(1-v), u*(1-v), (1-u)*v, u*v]
    return [(1-strength)*cs[0][j] + strength*sum(w*c[j] for w,c in zip(weights,cs[1:]))
            for j in range(3)]

def transform(c, saturation, brightness):
    y = sum(w*x for w,x in zip([.3,.5,.2],c))
    return [brightness*(y+saturation*(x-y)) for x in c]

max_error = 0
for iteration in range(1000):
    data = bytearray(rng.randbytes(528))
    for offset in offsets:
        struct.pack_into('<3f', data, offset, *[rng.uniform(0,3) for _ in range(3)])
    data = bytes(data)
    for mono, sat, val in [(0,0,.5),(1,1,1),(1,float('nan'),float('inf'))]:
        result, changed = prepare(data,mono,sat,val)
        assert result == data and not changed, 'identity or RGB guard failed'
    sat,val = rng.random(),rng.uniform(.25,1.5)
    result,changed = prepare(data,1,sat,val)
    assert changed
    touched = {offset+j for offset in offsets for j in range(12)}
    assert all(a==b for i,(a,b) in enumerate(zip(data,result)) if i not in touched), 'alpha/other field modified'
    u,v,strength = rng.random(),rng.random(),rng.random()
    expected = transform(rendered_tint(colors(data),u,v,strength),sat,val)
    actual = rendered_tint(colors(result),u,v,strength)
    error = max(abs(a-b) for a,b in zip(expected,actual))
    max_error = max(max_error,error)
    assert error < 2e-6
    neutral,_ = prepare(data,1,0,val)
    for c in colors(neutral): assert c[0] == c[1] == c[2]

print(json.dumps({'status':'PASS','cases':1000,'max_mix_commutation_error':max_error,
                  'validated':['source immutable','all five RGB triples','all alpha and unrelated bytes unchanged',
                               'RGB guard','default exact identity','invalid input identity',
                               'S=0 equal RGB','bilinear and content-aware blend equivalence'],
                  'scope':'offline kernel test; no Frame execution'},indent=2))
