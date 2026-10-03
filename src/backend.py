#!/usr/bin/python3
"""Framely JSON-line backend; manages only this plugin's per-user integration."""
import hashlib,json,math,os,pathlib,select,shlex,shutil,signal,subprocess,sys,tempfile,time
SUPPORTED={'ab33d32b15f55d356d6c4509b635fac6dca9614e6485226e75b62aaaa3aa639e','d75d3a0d3a86f8750e8f77fd43575605465c8fa2bef973a7597c4a1c8cb123b3'}
MARKER='# Managed by tooru.passthrough-color\n'
LEGACY_MARKER='# Managed by framely.passthrough-color\n'
DEFAULT={'enabled':False,'hue':.67,'saturation':1.,'brightness':1.,'originalHue':None}

def controls(params):
 if not isinstance(params,dict) or set(params)-{'hue','saturation','brightness'}:raise ValueError('无效调节参数')
 out={}
 for key,(low,high) in {'hue':(0,1),'saturation':(0,1),'brightness':(.25,1.5)}.items():
  if key in params:
   value=params[key]
   if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:raise ValueError(f'{key} 必须在 {low}–{high} 范围内')
   out[key]=float(value)
 return out

def atomic(path,data):
 path=pathlib.Path(path);fd,name=tempfile.mkstemp(prefix='.passthrough-',dir=path.parent)
 try:
  with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
  os.chmod(name,0o600);os.replace(name,path)
 finally:
  try:os.unlink(name)
  except FileNotFoundError:pass

def encode(value):return (json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n').encode()
def digest(path):
 h=hashlib.sha256()
 with pathlib.Path(path).open('rb') as stream:
  for block in iter(lambda:stream.read(262144),b''):h.update(block)
 return h.hexdigest()

class Backend:
 def __init__(self,payload=None,data=None,home=None,uid=None):
  self.uid=os.getuid() if uid is None else uid;self.payload=pathlib.Path(payload or pathlib.Path(__file__).resolve().parent);self.data=pathlib.Path(data or os.environ['FRAMELY_DATA_DIR']);self.home=pathlib.Path(home or os.environ['HOME']);self.data.mkdir(parents=True,exist_ok=True)
  self.runtime=pathlib.Path(f'/run/user/{self.uid}/framely-passthrough-color');self.cache=self.home/'.local/share/framely/passthrough-color';self.dropin=self.home/'.config/systemd/user/steamvr.service.d/80-framely-passthrough-color.conf';self.state=DEFAULT.copy();self.last_error='';self.last_hue=None;self.configured=False
  path=self.data/'settings.json'
  try:
   saved=json.loads(path.read_text());self.state.update(controls({k:saved[k] for k in ('hue','saturation','brightness') if k in saved}));self.state['enabled']=saved.get('enabled') is True
   original=saved.get('originalHue');self.state['originalHue']=controls({'hue':original})['hue'] if original is not None else None
  except FileNotFoundError:pass
  except Exception as error:self.last_error='保存的设置无效，已回到默认值：'+str(error)
  self.env={**os.environ,'XDG_RUNTIME_DIR':f'/run/user/{self.uid}','DBUS_SESSION_BUS_ADDRESS':f'unix:path=/run/user/{self.uid}/bus'}
 def save(self):atomic(self.data/'settings.json',encode(self.state))
 def command(self,args):
  result=subprocess.run(args,env=self.env,capture_output=True,text=True,timeout=5)
  if result.returncode:raise RuntimeError((result.stderr or result.stdout or '运行时命令失败').strip()[-1200:])
  return result.stdout
 def ready(self):
  try:return self.command(['systemctl','--user','is-active','steamvr.service','steam.service','gamescope-session.service']).splitlines()==['active']*3
  except (RuntimeError,subprocess.TimeoutExpired):return False
 def compositor(self):
  for proc in pathlib.Path('/proc').iterdir():
   if not proc.name.isdigit():continue
   try:
    if proc.stat().st_uid==self.uid and (proc/'comm').read_text().strip()=='vrcompositor':return int(proc.name),proc/'exe'
   except (OSError,ValueError):continue
  return None,None
 def runtime_dir(self):
  parent=self.runtime.parent
  if parent.stat().st_uid!=self.uid or parent.is_symlink():raise RuntimeError('当前 Steam 会话目录不可用')
  if self.runtime.is_symlink():raise RuntimeError('插件 runtime 目录不能是符号链接')
  self.runtime.mkdir(mode=0o700,exist_ok=True)
  if self.runtime.stat().st_uid!=self.uid:raise RuntimeError('插件 runtime 目录属主不正确')
  self.runtime.chmod(0o700)
 def sv(self,identity=False):
  self.runtime_dir();atomic(self.runtime/'settings.json',encode({'saturation':1 if identity else self.state['saturation'],'brightness':1 if identity else self.state['brightness']}))
 def helper(self):
  # Framely intentionally extracts only backend.entry as executable.
  if self.cache.is_symlink():raise RuntimeError('插件缓存目录不能为符号链接')
  self.cache.mkdir(parents=True,exist_ok=True);self.cache.chmod(0o700)
  for name in ('hue_control','libopenvr_api.so'):
   source=self.payload/name;target=self.cache/name
   if target.is_symlink():raise RuntimeError('辅助程序路径不能为符号链接')
   if not target.exists() or digest(source)!=digest(target):atomic(target,source.read_bytes())
   target.chmod(0o700)
  return self.cache/'hue_control'
 def hue(self,value=None):
  if not self.ready():raise RuntimeError('SteamVR 会话尚未就绪，未连接或启动运行时')
  result=self.command([str(self.helper()),'--get'] if value is None else [str(self.helper()),'--set',str(value)])
  # OpenVR may emit its own diagnostics before the helper's final JSON line.
  parsed=json.loads(result.strip().splitlines()[-1]);return controls({'hue':parsed['hue']})['hue']
 def configuration(self):
  return MARKER+'[Service]\nEnvironment="VRCOMPOSITOR_LD_PRELOAD='+str(self.cache/'libframely_passthrough_color.so')+'"\nEnvironment="FRAME_SV_ENABLE=1"\nEnvironment="FRAME_SV_CONTROL_FILE='+str(self.runtime/'settings.json')+'"\nEnvironment="FRAME_SV_STATUS_FILE='+str(self.runtime/'status.json')+'"\n'
 def setup(self):
  if self.uid==0:raise RuntimeError('插件必须以当前 Steam 会话用户运行')
  pid,exe=self.compositor();runtime_hash=digest(exe) if exe else digest('/opt/steamvr/bin/linuxarm64/vrcompositor')
  if runtime_hash not in SUPPORTED:raise RuntimeError('当前 SteamVR 版本不受支持，未配置渲染模块')
  if '"' in str(self.home) or '\n' in str(self.home):raise RuntimeError('不支持此 home 路径')
  if self.dropin.is_symlink():raise RuntimeError('已有 drop-in 为符号链接，未覆盖')
  if self.dropin.exists() and not self.dropin.read_text().startswith((MARKER,LEGACY_MARKER)):raise RuntimeError('同名 drop-in 不属于本插件，未覆盖')
  environments=shlex.split(self.command(['systemctl','--user','show','steamvr.service','--property=Environment','--value']))
  preload=next((s.split('=',1)[1] for s in environments if s.startswith('VRCOMPOSITOR_LD_PRELOAD=')),'')
  if preload and preload!=str(self.cache/'libframely_passthrough_color.so'):raise RuntimeError('已有其他 compositor preload 配置，未覆盖')
  if self.cache.is_symlink():raise RuntimeError('插件缓存目录不能为符号链接')
  self.cache.mkdir(parents=True,exist_ok=True);self.cache.chmod(0o700)
  source=self.payload/'libframely_passthrough_color.so';target=self.cache/source.name
  if target.is_symlink():raise RuntimeError('模块路径不能为符号链接')
  if not target.exists() or digest(source)!=digest(target):atomic(target,source.read_bytes());target.chmod(0o700)
  self.dropin.parent.mkdir(parents=True,exist_ok=True);atomic(self.dropin,self.configuration().encode());self.command(['systemctl','--user','daemon-reload']);self.configured=True
 def remove_configuration(self):
  if self.dropin.is_symlink():raise RuntimeError('拒绝删除符号链接 drop-in')
  if self.dropin.exists():
   if not self.dropin.read_text().startswith((MARKER,LEGACY_MARKER)):raise RuntimeError('拒绝删除其他程序的 drop-in')
   self.dropin.unlink();self.command(['systemctl','--user','daemon-reload'])
  self.configured=False
 def set(self,params):
  next_state={**self.state,**controls(params)}
  if not self.state['enabled']:self.state=next_state;self.save();return self.info()
  if next_state['hue']!=self.state['hue']:
   confirmed=self.hue(next_state['hue'])
   if abs(confirmed-next_state['hue'])>1e-5:raise RuntimeError('系统色相回读与设置不一致')
   self.last_hue=confirmed
  self.state=next_state;self.sv();self.save();return self.info()
 def enable(self,enabled):
  if not isinstance(enabled,bool):raise ValueError('enabled 必须是布尔值')
  if enabled:
   old=self.state.copy();original=self.hue() if not old['enabled'] else old['originalHue']
   try:
    self.setup();confirmed=self.hue(self.state['hue'])
    if abs(confirmed-self.state['hue'])>1e-5:raise RuntimeError('系统色相回读与设置不一致')
    self.state['originalHue']=original;self.state['enabled']=True;self.last_hue=confirmed;self.sv();self.save()
   except Exception:
    self.state=old
    if not old['enabled']:
     try:self.sv(identity=True);self.remove_configuration()
     except Exception:pass
     if original is not None:
      try:self.hue(original)
      except Exception:pass
    raise
  else:
   self.sv(identity=True);self.remove_configuration();self.state['enabled']=False;self.last_hue=None;self.save()
   if self.state['originalHue'] is not None and self.ready():self.hue(self.state['originalHue'])
  self.last_error=''
  return self.info()
 def tick(self):
  if not self.state['enabled']:return
  try:
   self.sv()
   if not self.configured:self.setup()
   if self.last_hue is None and self.ready():self.last_hue=self.hue(self.state['hue'])
   self.last_error=''
  except Exception as error:self.last_error=str(error)
 def info(self):
  pid,exe=self.compositor();runtime_hash=digest(exe) if exe else None;native=None
  try:
   status=json.loads((self.runtime/'status.json').read_text())
   if status['pid']==pid and status.get('active') is True:native=status
  except (OSError,ValueError,KeyError):pass
  return {'settings':self.state,'supported':runtime_hash in SUPPORTED if runtime_hash else None,'runtimeHash':runtime_hash,'nativeActive':bool(native),'matchedMono':native.get('matchedMono',0) if native else 0,'restartRequired':self.state['enabled'] and not native,'error':self.last_error,'connected':self.ready()}
 def handle(self,method,params):
  if method=='framely.lifecycle.start':return {'ready':True}
  if method=='framely.lifecycle.stop':self.stop();return {'stopped':True}
  if method=='status':return self.info()
  if method=='readHue':return {'hue':self.hue()}
  if method=='set':return self.set(params)
  if method=='enable':return self.enable(params.get('enabled'))
  if method=='reset':return self.set({'hue':self.state['originalHue'] if self.state['originalHue'] is not None else .67,'saturation':1,'brightness':1})
  raise ValueError('未知方法')
 def stop(self):
  # Neutralize a mapped module; it is never hot-unloaded or attached.
  try:self.sv(identity=True)
  except Exception:pass
  try:
   system=subprocess.run(['systemctl','is-system-running'],capture_output=True,text=True,timeout=1)
   # A persistent user drop-in is needed for the very first VR start after reboot.
   if system.stdout.strip()!='stopping':self.remove_configuration()
  except Exception:pass
  try:
   if self.state['enabled'] and self.state['originalHue'] is not None and self.ready():self.hue(self.state['originalHue'])
  except Exception:pass

def main():
 backend=Backend()
 if sys.argv[1:]==['--crash-cleanup']:
  backend.sv(identity=True);backend.remove_configuration()
  if backend.state['enabled'] and backend.state['originalHue'] is not None and backend.ready():backend.hue(backend.state['originalHue'])
  return
 stopping=False
 def stop(*_):
  nonlocal stopping;stopping=True
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop);last=0
 try:
  while not stopping:
   if time.monotonic()-last>2:backend.tick();last=time.monotonic()
   if not select.select([sys.stdin],[],[],.25)[0]:continue
   line=sys.stdin.readline()
   if not line:break
   request={}
   try:
    if len(line.encode())>65536:raise ValueError('请求过大')
    request=json.loads(line);params=request.get('params') or {};result=backend.handle(request['method'],params);reply={'id':request['id'],'result':result}
   except Exception as error:reply={'id':request.get('id'),'error':str(error)}
   print(json.dumps(reply,ensure_ascii=False,allow_nan=False),flush=True)
 finally:backend.stop()
if __name__=='__main__':main()
