import importlib.util,json,pathlib,tempfile,unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('color_backend',pathlib.Path(__file__).parents[1]/'src/backend.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class Color(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
  self.b=module.Backend(payload=self.root,data=self.root/'data',home=self.root/'home',uid=1000)
  self.b.runtime=self.root/'runtime';self.b.runtime_dir=lambda:self.b.runtime.mkdir(exist_ok=True)
  self.b.ready=lambda:True;self.b.compositor=lambda:(None,None)
  self.mode='off';self.b.camera=lambda mode=None:{'mode':self.mode,'colorAvailable':True}
 def tearDown(self):self.tmp.cleanup()
 def test_mode_does_not_read_compositor_or_client_hash(self):
  self.b.camera=module.Backend.camera.__get__(self.b)
  self.b.helper=lambda:pathlib.Path('/helper')
  self.b.command=lambda _:json.dumps({'mode':'color','colorAvailable':True})
  with patch.object(module,'digest',side_effect=AssertionError('global hash gate')):
   self.assertEqual(self.b.camera()['mode'],'color')
 def test_hue_survives_incompatible_native_renderer(self):
  with patch.object(self.b,'render_supported',return_value=False),patch.object(self.b,'setup') as setup,patch.object(self.b,'hue',side_effect=lambda v=None:.42 if v is None else v):
   self.b.enable(True);self.b.set({'hue':.3});self.b.tick();setup.assert_not_called()
   self.assertEqual(self.b.state['hue'],.3);self.assertTrue(self.b.state['enabled']);self.assertEqual(self.b.last_error,'')
 def test_mode_failure_does_not_change_render_capability(self):
  self.b.camera=lambda *args:(_ for _ in ()).throw(RuntimeError('mode ABI changed'))
  self.b.compositor=lambda:(123,pathlib.Path('/unlisted/compositor'))
  with patch.object(module,'digest',return_value='unlisted'),patch.object(self.b,'render_supported',return_value=True):
   status=self.b.info();self.assertTrue(status['supported']);self.assertIsNone(status['mode']);self.assertEqual(status['modeError'],'mode ABI changed')
 def test_color_ranges_and_invalid_fields(self):
  for params in [{'temperature':-1.1},{'temperature':float('nan')},{'saturation':2.1},{'brightness':True},{'hue':.4},{'enabled':True}]:
   with self.assertRaises(ValueError):module.color_controls(params)
  self.assertEqual(module.color_controls({'temperature':-1,'saturation':2,'brightness':1.5}),{'temperature':-1.,'saturation':2.,'brightness':1.5})
 def test_color_persistence_and_monochrome_independence(self):
  self.b.set({'hue':.1,'brightness':.75})
  self.b.color_set({'temperature':.5,'saturation':1.6,'brightness':1.2})
  other=module.Backend(payload=self.root,data=self.root/'data',home=self.root/'home',uid=1000)
  self.assertEqual(other.state['hue'],.1);self.assertEqual(other.state['brightness'],.75)
  self.assertEqual(other.color['saturation'],1.6);self.assertEqual(other.color['temperature'],.5)
 def test_migrate_legacy_monochrome_settings(self):
  (self.root/'data/settings.json').write_text(json.dumps({'enabled':True,'hue':.2,'saturation':0,'brightness':1.3,'originalHue':.67}))
  other=module.Backend(payload=self.root,data=self.root/'data',home=self.root/'home',uid=1000)
  self.assertEqual(other.state['brightness'],1.3);self.assertEqual(other.color,module.COLOR_DEFAULT)
 def test_mode_follows_actual_runtime_not_saved_preferences(self):
  for self.mode in ['off','color','mono']:
   self.assertEqual(self.b.info()['mode'],self.mode)
  with self.assertRaises(ValueError):self.b.set_mode('invented')
  with self.assertRaises(RuntimeError):self.b.set_mode('color') if self.mode=='mono' else self.b.set_mode('mono')
 def test_color_enable_never_changes_monochrome_hue(self):
  with patch.object(self.b,'setup'),patch.object(self.b,'hue') as hue:
   self.b.color_enable(True);hue.assert_not_called()
  self.assertEqual(json.loads((self.b.runtime/'settings.json').read_text()),{'saturation':1,'brightness':1})
  self.b.color_set({'brightness':1.4,'temperature':.7})
  with patch.object(self.b,'remove_configuration') as remove:
   self.b.enable(False);remove.assert_not_called()
  self.assertEqual(json.loads((self.b.runtime/'color.json').read_text())['brightness'],1.4)
 def test_color_reset_and_disable_restore_identity(self):
  self.b.color['enabled']=True;self.b.color_set({'saturation':0,'brightness':1.4,'temperature':1})
  self.b.handle('color.reset',{});self.assertTrue(self.b.color['enabled'])
  self.assertEqual({k:self.b.color[k] for k in ('saturation','brightness','temperature')},{'saturation':1,'brightness':1,'temperature':0})
  with patch.object(self.b,'remove_configuration'):self.b.color_enable(False)
  self.assertEqual(json.loads((self.b.runtime/'color.json').read_text()),{'saturation':1,'brightness':1,'temperature':0})
if __name__=='__main__':unittest.main()
