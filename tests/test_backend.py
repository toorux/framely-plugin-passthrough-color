import importlib.util,json,math,pathlib,tempfile,unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('backend',pathlib.Path(__file__).parents[1]/'src/backend.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class Backend(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name);self.backend=module.Backend(payload=self.root,data=self.root/'data',home=self.root/'home',uid=1000);self.backend.runtime=self.root/'runtime';self.backend.runtime_dir=lambda:self.backend.runtime.mkdir(exist_ok=True);self.backend.ready=lambda:True;self.backend.compositor=lambda:(None,None)
 def tearDown(self):self.temp.cleanup()
 def test_extracted_helper_gets_executable_private_copy(self):
  for name in ('hue_control','libopenvr_api.so'):(self.root/name).write_bytes(b'test')
  helper=self.backend.helper();self.assertEqual(helper.read_bytes(),b'test');self.assertEqual(helper.stat().st_mode&0o777,0o700)
  helper.unlink();helper.symlink_to(self.root/'hue_control')
  with self.assertRaises(RuntimeError):self.backend.helper()
 def test_shutdown_keeps_startup_configuration(self):
  self.backend.dropin.parent.mkdir(parents=True);self.backend.dropin.write_text(module.MARKER+'[Service]\n');self.backend.state['enabled']=True;self.backend.state['originalHue']=.42
  self.backend.hue=lambda value=None:.42
  with patch.object(module.subprocess,'run',return_value=type('Result',(),{'stdout':'stopping\n'})()):self.backend.stop()
  self.assertTrue(self.backend.dropin.exists());self.assertEqual(json.loads((self.root/'runtime/settings.json').read_text()),{'saturation':1,'brightness':1})
 def test_normal_stop_removes_startup_configuration(self):
  self.backend.dropin.parent.mkdir(parents=True);self.backend.dropin.write_text(module.MARKER+'[Service]\n');self.backend.command=lambda _:''
  with patch.object(module.subprocess,'run',return_value=type('Result',(),{'stdout':'running\n'})()):self.backend.stop()
  self.assertFalse(self.backend.dropin.exists())
 def test_renamed_plugin_recognizes_its_legacy_configuration(self):
  self.backend.dropin.parent.mkdir(parents=True);self.backend.dropin.write_text(module.LEGACY_MARKER+'[Service]\n');self.backend.command=lambda _:''
  self.assertTrue(self.backend.configuration().startswith('# Managed by tooru.passthrough-color\n'))
  self.backend.remove_configuration()
  self.assertFalse(self.backend.dropin.exists())
 def test_ranges_and_nonfinite_are_rejected(self):
  for key,value in [('hue',1.1),('hue',float('nan')),('saturation',-1),('brightness',.1),('brightness',float('inf')),('hue',True),('unknown',1)]:
   with self.assertRaises(ValueError):module.controls({key:value})
 def test_preferences_save_atomically_and_reload(self):
  self.backend.set({'saturation':0,'brightness':1.3});saved=json.loads((self.root/'data/settings.json').read_text());self.assertEqual(saved['saturation'],0);self.assertFalse((self.root/'runtime/settings.json').exists());new=module.Backend(payload=self.root,data=self.root/'data',home=self.root/'home',uid=1000);self.assertEqual(new.state['brightness'],1.3)
 def test_enable_disable_restore_actual_original_hue(self):
  calls=[];self.backend.setup=lambda:None;self.backend.remove_configuration=lambda:None;self.backend.hue=lambda value=None:calls.append(value) or (.42 if value is None else value)
  self.backend.enable(True);self.assertEqual(self.backend.state['originalHue'],.42);self.backend.set({'hue':.1,'saturation':0});self.assertEqual(json.loads((self.root/'runtime/settings.json').read_text())['saturation'],0)
  self.backend.enable(False);self.assertEqual(calls[-1],.42);self.assertEqual(json.loads((self.root/'runtime/settings.json').read_text()),{'saturation':1,'brightness':1});self.assertFalse(self.backend.state['enabled'])
 def test_foreign_dropin_and_preload_are_not_overwritten(self):
  self.backend.dropin.parent.mkdir(parents=True);self.backend.dropin.write_text('foreign config');
  with self.assertRaises(RuntimeError):self.backend.remove_configuration()
  self.assertEqual(self.backend.dropin.read_text(),'foreign config')
  self.backend.dropin.unlink();self.backend.command=lambda _: 'VRCOMPOSITOR_LD_PRELOAD=/other/plugin.so'
  with patch.object(module,'digest',return_value=next(iter(module.SUPPORTED))):
   with self.assertRaises(RuntimeError):self.backend.setup()
  self.assertFalse(self.backend.dropin.exists())
 def test_failed_hue_readback_does_not_save_new_controls(self):
  self.backend.state['enabled']=True;self.backend.hue=lambda _: .8
  with self.assertRaises(RuntimeError):self.backend.set({'hue':.1})
  self.assertEqual(self.backend.state['hue'],.67)
 def test_unsupported_runtime_is_rejected_before_configuration(self):
  with patch.object(module,'digest',return_value='0'*64):
   with self.assertRaises(RuntimeError):self.backend.setup()
  self.assertFalse(self.backend.dropin.exists())
 def test_lifecycle_start_and_stop_use_existing_cleanup(self):
  self.assertEqual(self.backend.handle('framely.lifecycle.start',{}),{'ready':True})
  with patch.object(self.backend,'stop') as stop:
   self.assertEqual(self.backend.handle('framely.lifecycle.stop',{}),{'stopped':True});stop.assert_called_once()
 def test_crash_cleanup_exits_without_tick_or_vr_restart(self):
  with patch.object(module,'Backend',return_value=self.backend),patch.object(module.sys,'argv',['backend.py','--crash-cleanup']),patch.object(self.backend,'sv') as reset,patch.object(self.backend,'remove_configuration') as remove,patch.object(self.backend,'tick') as tick,patch.object(self.backend,'setup') as setup:
   module.main();reset.assert_called_once_with(identity=True);remove.assert_called_once();tick.assert_not_called();setup.assert_not_called()
 def test_crash_cleanup_does_not_remove_foreign_configuration(self):
  self.backend.dropin.parent.mkdir(parents=True);self.backend.dropin.write_text('foreign')
  with patch.object(module,'Backend',return_value=self.backend),patch.object(module.sys,'argv',['backend.py','--crash-cleanup']):
   with self.assertRaises(RuntimeError):module.main()
  self.assertEqual(self.backend.dropin.read_text(),'foreign')
if __name__=='__main__':unittest.main()
