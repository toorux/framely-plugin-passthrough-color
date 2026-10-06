import {build} from 'esbuild';import {mkdir,copyFile} from 'node:fs/promises';import {execFileSync} from 'node:child_process';
await mkdir('payload',{recursive:true});
execFileSync('cc',['-std=c11','-O2','-Wall','-Wextra','-Werror','-fPIC','-shared','-pthread','native/frame_sv_module.c','native/frame_compat.c','native/frame_sv_uniform.c','native/frame_color_uniform.c','native/frame_color_shader.c','native/frame_sv_entry.S','-ldl','-lm','-o','payload/libframely_passthrough_color.so'],{stdio:'inherit'});
const openvr='vendor/openvr';
execFileSync('c++',['-std=c++17','-O2','-Wall','-Wextra','-Werror','-Inative','-I'+openvr,'native/hue_control.cpp','-L'+openvr+'/lib/linuxarm64','-lopenvr_api','-ldl','-Wl,-rpath,$ORIGIN','-o','payload/hue_control'],{stdio:'inherit'});
await copyFile(openvr+'/lib/linuxarm64/libopenvr_api.so','payload/libopenvr_api.so');await copyFile(openvr+'/LICENSE','payload/OPENVR-LICENSE.txt');await copyFile('src/backend.py','payload/backend.py');
await build({entryPoints:['src/page.tsx'],bundle:true,minify:true,loader:{'.css':'text'},outfile:'payload/page.js',define:{'process.env.NODE_ENV':'"production"'}});
execFileSync('python3',['scripts/icon.py'],{stdio:'inherit'});console.log('Built plugin-package payload; no runtime connected or restarted.');
