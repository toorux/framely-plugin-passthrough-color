#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdatomic.h>
#include "frame_shader_structure.h"

/* Only fingerprinted passthrough shaders are changed, in memory at creation.
 * Their vertex partners never read member 25 (verified fingerprints in README).
 * Member 25[0].w is unused by both original RGB fragments and carries S.
 */
extern void frame_sv_hash_bytes(const void *,size_t,unsigned char[32]);
static _Atomic unsigned enabled,shader_mask;
void frame_color_shader_enable(void){atomic_store(&enabled,1);}
unsigned frame_color_shader_mask(void){return atomic_load(&shader_mask);}
static int shader_structure(const uint32_t* words,size_t count,uint32_t refs[10]){
 if(words[3]<1||words[3]>8192)return 0;
 uint32_t* map=calloc(words[3],4);uint32_t* reverse=calloc(words[3],4);uint32_t* normalized=malloc(count*4);
 if(!map||!reverse||!normalized){free(map);free(reverse);free(normalized);return 0;}
 size_t at=0;uint32_t next=0;int kind=0;
 for(size_t i=5;i<count;){unsigned n=words[i]>>16,op=words[i]&65535;if(!n||n>count-i)goto done;
  if(shader_metadata(op)){i+=n;continue;}
  uint32_t mask;unsigned tail;if(!shader_ids(words+i,n,&mask,&tail))goto done;
  memcpy(normalized+at,words+i,n*4);
  for(unsigned j=1;j<n;j++)if((j<32&&(mask>>j&1))||(tail&&j>=tail)||(op==251&&j>=4&&!(j&1))){
   uint32_t id=words[i+j];if(!id||id>=words[3])goto done;
   if(!map[id]){if(next+1>=words[3])goto done;map[id]=++next;reverse[next]=id;}
   normalized[at+j]=map[id];
  }
  at+=n;i+=n;
 }
 unsigned char digest[32];frame_sv_hash_bytes(normalized,at*4,digest);
 const uint32_t* profile=0;
 if(!memcmp(digest,shader_hash_0,32)){kind=1;profile=shader_refs_0;}
 else if(!memcmp(digest,shader_hash_1,32)){kind=2;profile=shader_refs_1;}
 if(profile)for(unsigned j=0;j<10;j++){if(profile[j]>next){kind=0;break;}refs[j]=reverse[profile[j]];}
 done:free(map);free(reverse);free(normalized);return kind;
}

/* Returns owned words, or NULL to preserve the original module. */
uint32_t *frame_color_patch(const uint32_t* words,size_t bytes,size_t* result_bytes,unsigned* kind){
 if(!words||bytes<20||bytes%4||bytes>20000||words[0]!=0x07230203)return 0;
 uint32_t refs[10];int profile=shader_structure(words,bytes/4,refs);if(!profile)return 0;
 uint32_t scalar=refs[0],vector=refs[1],ptr=refs[2],ubo=refs[3],index25=refs[4],index0=refs[5],index3=refs[6];
 uint32_t pixel=refs[7],result=refs[8],glsl=refs[9],bound=words[3];size_t function=0,target=0,count=bytes/4;
 for(size_t i=5;i<count;){unsigned n=words[i]>>16,op=words[i]&65535;if(!n||n>count-i)return 0;if(op==54&&!function)function=i;if(op==133&&n==5&&words[i+2]==result&&words[i+3]==pixel)target=i;i+=n;}
 if(!function||!target||bound>UINT32_MAX-11)return 0;
 float w[]={.2126f,.7152f,.0722f};uint32_t bits[3];memcpy(bits,w,sizeof(bits));
 uint32_t constants[]={ (4u<<16)|43,scalar,bound,bits[0],(4u<<16)|43,scalar,bound+1,bits[1],(4u<<16)|43,scalar,bound+2,bits[2],(6u<<16)|44,vector,bound+3,bound,bound+1,bound+2 };
 uint32_t code[]={
  (7u<<16)|65,ptr,bound+4,ubo,index25,index0,index3,
  (4u<<16)|61,scalar,bound+5,bound+4,
  (5u<<16)|148,scalar,bound+6,pixel,bound+3,
  (6u<<16)|80,vector,bound+7,bound+6,bound+6,bound+6,
  (6u<<16)|80,vector,bound+8,bound+5,bound+5,bound+5,
  /* GLSL.std.450 FMix in linear RGB: grey*(1-S) + RGB*S. */
  (8u<<16)|12,vector,bound+9,glsl,46,bound+7,pixel,bound+8
 };
 size_t extra=sizeof(constants)+sizeof(code);uint32_t* out=malloc(bytes+extra);if(!out)return 0;
 memcpy(out,words,function*4);size_t at=function;memcpy(out+at,constants,sizeof(constants));at+=sizeof(constants)/4;
 memcpy(out+at,words+function,(target-function)*4);at+=target-function;memcpy(out+at,code,sizeof(code));at+=sizeof(code)/4;
 memcpy(out+at,words+target,(count-target)*4);out[at+3]=bound+9;out[3]=bound+10;
 *result_bytes=bytes+extra;*kind=(unsigned)profile;return out;
}

/* Vulkan's dispatchable handles are pointers on Linux ARM64. */
typedef void (*Proc)(void);
typedef Proc (*GetProc)(void*,const char*);
typedef struct {uint32_t sType;const void* pNext;uint32_t flags;size_t codeSize;const uint32_t* pCode;} ShaderInfo;
typedef int (*Create)(void*,const ShaderInfo*,const void*,uint64_t*);
static _Atomic(GetProc) real_instance,real_device;
static _Atomic(Create) real_create;
static int create_shader(void* device,const ShaderInfo* info,const void* allocator,uint64_t* module){
 Create real=atomic_load(&real_create);if(!real)return -3;
 size_t size=0;unsigned kind=0;uint32_t* code=atomic_load(&enabled)&&info?frame_color_patch(info->pCode,info->codeSize,&size,&kind):0;
 ShaderInfo patched;if(code){patched=*info;patched.codeSize=size;patched.pCode=code;info=&patched;}
 int result=real(device,info,allocator,module);if(!result&&code)atomic_fetch_or(&shader_mask,kind);free(code);return result;
}
static Proc instance_proc(void*,const char*);
static Proc device_proc(void*,const char*);
static Proc wrap(const char* name,Proc real){
 if(!real||!atomic_load(&enabled))return real;
 if(!strcmp(name,"vkCreateShaderModule")){atomic_store(&real_create,(Create)real);return (Proc)create_shader;}
 if(!strcmp(name,"vkGetDeviceProcAddr")){atomic_store(&real_device,(GetProc)real);return (Proc)device_proc;}
 if(!strcmp(name,"vkGetInstanceProcAddr")){atomic_store(&real_instance,(GetProc)real);return (Proc)instance_proc;}
 return real;
}
static Proc instance_proc(void* instance,const char* name){GetProc real=atomic_load(&real_instance);return real?wrap(name,real(instance,name)):0;}
static Proc device_proc(void* device,const char* name){GetProc real=atomic_load(&real_device);return real?wrap(name,real(device,name)):0;}
/* Compositor obtains Vulkan functions with dlsym instead of linking Vulkan. */
void* dlsym(void* handle,const char* name){
 typedef void*(*Lookup)(void*,const char*);Lookup real=(Lookup)dlvsym(RTLD_NEXT,"dlsym","GLIBC_2.17");
 if(!real)return 0;
 return (void*)wrap(name,(Proc)real(handle,name));
}
