import React from 'react';

export function Button(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type="button" {...props}/>;
}
export function Section({title,children}:{title:string;children:React.ReactNode}) {
  return <section className="settings-section"><h2>{title}</h2>{children}</section>;
}
export function Notice({children,error=false}:{children:React.ReactNode;error?:boolean}) {
  return <div className={error?'notice error':'notice'} role={error?'alert':'status'}>{children}</div>;
}
export function Toggle({label,description,checked,onChange,disabled=false}:{label:string;description?:string;checked:boolean;onChange:(value:boolean)=>void;disabled?:boolean}) {
  return <label className="setting-toggle"><span><b>{label}</b>{description&&<small>{description}</small>}</span><input type="checkbox" role="switch" checked={checked} disabled={disabled} onChange={e=>onChange(e.target.checked)}/></label>;
}
export function Slider({label,value,onChange,min=0,max=100,step=1,disabled=false}:{label:string;value:number;onChange:(value:number)=>void;min?:number;max?:number;step?:number;disabled?:boolean}) {
  return <label className="slider"><span>{label}<output>{value}</output></span><input type="range" min={min} max={max} step={step} value={value} disabled={disabled} onChange={e=>onChange(+e.target.value)}/></label>;
}
export function Tabs({value,onChange,tabs}:{value:string;onChange:(value:string)=>void;tabs:{id:string;label:string}[]}) {
  return <nav className="section-nav" aria-label="相机管理">{tabs.map(t=><Button key={t.id} aria-current={value===t.id?'page':undefined} className={value===t.id?'active':''} onClick={()=>onChange(t.id)}>{t.label}</Button>)}</nav>;
}
export function Mark({camera=false}:{camera?:boolean}) {
  return <span className="plugin-mark" aria-hidden="true"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">{camera?<><path d="M4 6h4l2-3h4l2 3h4v14H4z"/><circle cx="12" cy="12" r="4"/></>:<><circle cx="12" cy="12" r="9"/><path d="M12 3v18M3 12h18"/><path d="M12 3a15 15 0 0 1 0 18"/></>}</svg></span>;
}
