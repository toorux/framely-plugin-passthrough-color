import React,{useEffect,useRef,useState} from 'react';
import {registerPlugin,framely,Button,Section,Slider,Toggle,Notice} from '@framely/sdk';
import css from './style.css';
const sheet=document.createElement('style');sheet.textContent=css;document.head.append(sheet);
type Controls={hue:number;saturation:number;brightness:number};
type State={settings:Controls&{enabled:boolean;originalHue:number|null};nativeActive:boolean;connected:boolean;supported:boolean|null;restartRequired:boolean;matchedMono:number;error:string};
const adjustmentValues=({hue,saturation,brightness}:Controls):Controls=>({hue,saturation,brightness});
function Page(){
 const[info,setInfo]=useState<State|null>(null),[draft,setDraft]=useState<Controls>({hue:.67,saturation:1,brightness:1}),[error,setError]=useState(''),[saving,setSaving]=useState(false),[working,setWorking]=useState(false);
 const pending=useRef<Controls|null>(null),timer=useRef<ReturnType<typeof setTimeout>|null>(null),sending=useRef(false),alive=useRef(true),initialized=useRef(false);
 useEffect(()=>{alive.current=true;async function refresh(){try{const result=await framely.call<State>('status');if(alive.current){setInfo(result);if(!initialized.current){initialized.current=true;setDraft(adjustmentValues(result.settings));}}}catch(e){if(alive.current)setError(String(e));}}void refresh();const interval=setInterval(()=>void refresh(),2500);return()=>{alive.current=false;clearInterval(interval);if(timer.current)clearTimeout(timer.current);};},[]);
 async function flush(rethrow=false){if(sending.current)return;sending.current=true;setSaving(true);try{while(pending.current){const values=pending.current;pending.current=null;const result=await framely.call<State>('set',adjustmentValues(values));if(alive.current){setInfo(result);setError('');}}}catch(e){pending.current=null;if(alive.current)setError(String(e));if(rethrow)throw e;}finally{sending.current=false;if(alive.current)setSaving(false);}}
 function change(values:Controls){setDraft(values);pending.current=adjustmentValues(values);if(timer.current)clearTimeout(timer.current);timer.current=setTimeout(()=>void flush(),250);}
 async function action(method:string,params:unknown={}){if(timer.current)clearTimeout(timer.current);setWorking(true);setError('');try{while(sending.current)await new Promise(r=>setTimeout(r,30));if(pending.current)await flush(true);while(sending.current)await new Promise(r=>setTimeout(r,30));const result=await framely.call<State>(method,params);if(alive.current){setInfo(result);setDraft(adjustmentValues(result.settings));}}catch(e){if(alive.current)setError(String(e));}finally{if(alive.current)setWorking(false);}}
 const blocked=working||!info||(info.settings.enabled&&(!info.connected||info.supported===false));
 return <><div className="color-title"><span className="color-wheel"/><div><h1>透视调色</h1><small>让黑白透视呈现更合适的色调。</small></div></div>{error&&<Notice error>{error}</Notice>}{info?.error&&<Notice error>{info.error}</Notice>}{info?.supported===false&&<Notice error>此 SteamVR 版本尚未适配，调色模块不会启用。</Notice>}
 <Section title="调色"><Toggle label="启用调色" checked={info?.settings.enabled??false} disabled={working||saving||!info||!info.connected||info.supported===false} onChange={enabled=>void action('enable',{enabled})} description={info?.settings.enabled?'停用后恢复启用前的色调与原始亮度。':'使用当前 Steam 会话权限，无需 root。'}/>
 {info?.restartRequired&&<Notice>首次启用的饱和度与亮度将在下次 SteamVR 启动后生效。色调可立即调整；插件不会自动重启 SteamVR。</Notice>}{info?.settings.enabled&&info.nativeActive&&<p className="status"><i/>调色模块已启用{info.matchedMono===0?' · 等待打开透视':''}</p>}
 <div className="tone-preview" style={{background:`hsl(${draft.hue*360} ${draft.saturation*70}% ${Math.min(75,45*draft.brightness)}%)`}}><span>色调示意</span></div>
 <Slider label="色调（°）" value={Math.round(draft.hue*360)} min={0} max={360} step={1} disabled={blocked||draft.saturation===0&&!!info?.nativeActive} onChange={degrees=>change({...draft,hue:degrees/360})}/>
 <Slider label="染色饱和度（%）" value={Math.round(draft.saturation*100)} min={0} max={100} step={1} disabled={blocked} onChange={value=>change({...draft,saturation:value/100})}/>
 <Slider label="亮度（%）" value={Math.round(draft.brightness*100)} min={25} max={150} step={1} disabled={blocked} onChange={value=>change({...draft,brightness:value/100})}/>
 <p className="save-state" role="status">{saving?'正在应用…':pending.current?'等待应用…':'设置自动保存'}</p></Section>
 <Section title="预设"><div className="presets"><Button disabled={blocked} onClick={()=>change({...draft,saturation:0,brightness:1})}>中性黑白</Button><Button disabled={blocked} onClick={()=>change({hue:.08,saturation:.3,brightness:1})}>柔和暖色</Button><Button disabled={blocked} onClick={()=>change({hue:.58,saturation:.3,brightness:1})}>柔和冷色</Button><Button disabled={blocked||saving} onClick={()=>void action('reset')}>恢复原始效果</Button></div></Section>
 <details className="help"><summary>如何调整</summary><p>先启用调色。首次启用后重新进入 SteamVR，看到“调色模块已启用”即可调节全部参数。以后调整不需要重启。</p><p>色调选择染色颜色；饱和度 0% 为中性黑白，100% 保留系统染色强度。黑白摄像头不会因此产生真实彩色画面。</p><p>亮度 100% 保持原始增益；高于 100% 可能让亮部丢失细节。中性黑白预设不修改摄像头或整个 Steam 界面的显示参数。</p><p>停用会恢复启用前的色调和原始饱和度、亮度，并取消下次启动的模块配置。卸载前请先停用；已载入的模块将在 SteamVR 下次关闭时退出。</p><p>设置会保存，并在插件启动后恢复。系统更新不匹配时会停止启用模块，等待插件适配。</p></details></>;
}
registerPlugin({QuickPage:Page});
