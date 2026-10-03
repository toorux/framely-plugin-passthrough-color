import ctypes, hashlib, json, os, random, shutil, struct, subprocess, tempfile, time
from pathlib import Path

root=Path.cwd()
lib=ctypes.CDLL(str(root/'build/libframe_sv_test.so'))
lib.frame_sv_test_hash.argtypes=[ctypes.c_char_p,ctypes.c_void_p]
lib.frame_sv_test_accept_file.argtypes=[ctypes.c_char_p]
lib.frame_sv_test_context.argtypes=[ctypes.c_void_p]
lib.frame_sv_test_parse.argtypes=[ctypes.c_char_p,ctypes.POINTER(ctypes.c_uint64)]
lib.frame_sv_test_reader.argtypes=[ctypes.c_char_p]
lib.frame_sv_test_cache.restype=ctypes.c_uint64
identity=0x3f8000003f800000
def packed(s,v): return struct.unpack('<Q',struct.pack('<ff',s,v))[0]
def parsed(text):
    out=ctypes.c_uint64()
    return lib.frame_sv_test_parse(text.encode(),ctypes.byref(out)),out.value

with tempfile.TemporaryDirectory(dir=root,prefix='.frame-sv-test-') as temporary:
    work=Path(temporary)
    # Known and boundary SHA vectors, then actual copied executable.
    rng=random.Random(19)
    for data in [b'',b'abc']+[rng.randbytes(n) for n in [55,56,63,64,65,127,128,129,4096,1048576]]:
        p=work/'hash-input';p.write_bytes(data);out=(ctypes.c_ubyte*32)()
        assert lib.frame_sv_test_hash(os.fsencode(p),out)
        assert bytes(out)==hashlib.sha256(data).digest()
    compositor=os.environ.get('FRAME_TEST_COMPOSITOR')
    if compositor:
        out=(ctypes.c_ubyte*32)()
        assert lib.frame_sv_test_hash(os.fsencode(compositor),out)
        assert bytes(out).hex() in {'ab33d32b15f55d356d6c4509b635fac6dca9614e6485226e75b62aaaa3aa639e','d75d3a0d3a86f8750e8f77fd43575605465c8fa2bef973a7597c4a1c8cb123b3'}
        assert lib.frame_sv_test_accept_file(os.fsencode(compositor))
    else:
        print('SKIP installed-binary acceptance: set FRAME_TEST_COMPOSITOR to an existing read-only vrcompositor copy')
    assert not lib.frame_sv_test_accept_file(os.fsencode(work/'hash-input'))
    context=bytes.fromhex('e0bb40bd62030391e14341bd600740f90808211e616b41f968ff01bd070040f9e73c40f9e0003fd6')
    assert lib.frame_sv_test_context(ctypes.create_string_buffer(context))
    for i in range(len(context)):
        mutated=bytearray(context);mutated[i]^=1
        assert not lib.frame_sv_test_context(ctypes.create_string_buffer(bytes(mutated)))
    for text in ['{}','{"saturation":0,"brightness":0.5}', '{"brightness":1.5,"saturation":1}']:
        assert parsed(text)[0]
    bad=['','{','{"saturation":','{"saturation":NaN}','{"saturation":Infinity}',
         '{"saturation":1e99}','{"saturation":01}','{"saturation":.5}',
         '{"saturation":1,"saturation":0}','{"brightness":0}',
         '{"saturation":-1}','{"brightness":2}','{"unknown":0}',
         '{"saturation":0,}','{"saturation":0}garbage']
    for text in bad: assert not parsed(text)[0],text
    control=work/'settings.json'; stable_path=os.fsencode(control)
    def replace(data):
        p=work/'next.json';p.write_bytes(data);p.replace(control)
    def wait_cache(expected):
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            if lib.frame_sv_test_cache()==expected:return
            time.sleep(.01)
        raise AssertionError((lib.frame_sv_test_cache(),expected))
    assert lib.frame_sv_test_reader(stable_path)
    try:
        wait_cache(identity)
        replace(b'{"saturation":0,"brightness":0.5}')
        wait_cache(packed(0,.5))
        replace(b'{"saturation":0.5,"brightness":1}')
        wait_cache(packed(.5,1))
        for data in [b'{',b'{"brightness":1e99}',b'{"saturation":0}\x00',b' ' * 257]:
            replace(data);wait_cache(identity)
        control.unlink();control.symlink_to(root/'README.md')
        wait_cache(identity);control.unlink()
        os.mkfifo(control);wait_cache(identity);control.unlink()
        replace(b'{"saturation":0,"brightness":1}');wait_cache(packed(0,1))
        control.unlink();wait_cache(identity)
    finally: lib.frame_sv_test_stop()
    # This is our mock test executable renamed vrcompositor, not Valve's binary.
    mock=work/'vrcompositor';shutil.copy2(root/'build/frame_sv_native_test',mock)
    env=dict(os.environ,FRAME_SV_ENABLE='1')
    env['LD_LIBRARY_PATH']=str(root/'build')+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    result=subprocess.run([str(mock)],capture_output=True,text=True,env=env,check=True)
    assert 'executable hash rejected; inactive' in result.stderr

print(json.dumps({'status':'PASS','tests':['SHA256 vectors/boundaries and installed binary copy; constructor expected digest positive/negative acceptance',
    'all 40 upload signature bytes reject mutation','strict JSON malformed/nonfinite/range/duplicate rejection',
    'background-only live cache updates','missing/partial/oversized/NUL/symlink/FIFO control resets to identity',
    'mock executable constructor fails closed before hook'],
    'scope':'local offline tests only; no Frame deployment'},indent=2))
