#define _GNU_SOURCE
#include <assert.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
typedef void (*Upload)(void*,void*,const void*);
extern int frame_sv_abi_test(void*,void*,const void*,void*,Upload,void*);
extern void *frame_sv_test_entry(void);
extern void frame_sv_test_bind(Upload,uintptr_t);
extern void frame_sv_test_publish(float,float);
extern void *frame_sv_test_veneer(uintptr_t,size_t);
extern int frame_sv_test_patch(uintptr_t,void*,size_t);
extern int frame_sv_prepare(void*,const void*,int,float,float);
static uintptr_t vtable=0x11223344;
struct Context { unsigned char node[848]; unsigned char expected[528]; int identity,nest; unsigned calls; void *path; };
static _Thread_local unsigned nested;
static void mock_upload(void *iface,void *buffer,const void *data) {
    struct Context *ctx=buffer;
    assert(iface==&vtable);
    assert(!memcmp(data,nested?ctx->node+192:ctx->expected,528));
    if(ctx->identity||nested) assert(data==ctx->node+192);
    else assert(data!=ctx->node+192);
    ++ctx->calls;
    if(ctx->nest&&!nested) {
        unsigned char held[528]; memcpy(held,data,528);
        nested=1;
        assert(!frame_sv_abi_test(&vtable,ctx,ctx->node+192,ctx->node,mock_upload,ctx->path));
        nested=0;
        assert(!memcmp(held,data,528));
    }
}
static void fill(struct Context *ctx,unsigned seed) {
    memset(ctx,0,sizeof(*ctx));
    for(unsigned i=0;i<528;++i) ctx->node[192+i]=(unsigned char)(i+seed);
    unsigned offsets[]={304,464,480,496,512};
    for(unsigned k=0;k<5;++k) {float c[3]={.2f+seed*.01f,.4f+k*.01f,.8f};memcpy(ctx->node+192+offsets[k],c,12);}
    ctx->node[839]=1;ctx->path=frame_sv_test_entry();
}
static void *stress(void *arg) {
    struct Context ctx;fill(&ctx,(unsigned)(uintptr_t)arg);
    frame_sv_prepare(ctx.expected,ctx.node+192,1,.5f,.75f);
    for(unsigned i=0;i<10000;++i) assert(!frame_sv_abi_test(&vtable,&ctx,ctx.node+192,ctx.node,mock_upload,ctx.path));
    assert(ctx.calls==10000);return 0;
}
int main(void) {
    frame_sv_test_bind(mock_upload,vtable);
    struct Context ctx;fill(&ctx,1);
    frame_sv_test_publish(1,1);ctx.identity=1;memcpy(ctx.expected,ctx.node+192,528);
    assert(!frame_sv_abi_test(&vtable,&ctx,ctx.node+192,ctx.node,mock_upload,ctx.path));
    frame_sv_test_publish(.5f,.75f);ctx.identity=0;
    frame_sv_prepare(ctx.expected,ctx.node+192,1,.5f,.75f);
    assert(!frame_sv_abi_test(&vtable,&ctx,ctx.node+192,ctx.node,mock_upload,ctx.path));
    unsigned char source[528];memcpy(source,ctx.node+192,528);ctx.nest=1;
    assert(!frame_sv_abi_test(&vtable,&ctx,ctx.node+192,ctx.node,mock_upload,ctx.path));
    assert(!memcmp(source,ctx.node+192,528));ctx.nest=0;
    pthread_t threads[4];for(unsigned i=0;i<4;++i) assert(!pthread_create(&threads[i],0,stress,(void*)(uintptr_t)i));
    for(unsigned i=0;i<4;++i) assert(!pthread_join(threads[i],0));
    /* Real RX synthetic code page. Only its BLR x7 is changed, then executed.
     * No installed Frame code or process is used.
     */
    size_t page=(size_t)sysconf(_SC_PAGESIZE);
    uint32_t *code=mmap(0,page,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);assert(code!=MAP_FAILED);
    uint32_t words[]={0xa9bf7bfd,0xd63f00e0,0xa8c17bfd,0xd65f03c0};memcpy(code,words,sizeof(words));
    __builtin___clear_cache((char*)code,(char*)code+16);assert(!mprotect(code,page,PROT_READ|PROT_EXEC));
    void *veneer=frame_sv_test_veneer((uintptr_t)(code+1),page);assert(veneer);
    assert(frame_sv_test_patch((uintptr_t)(code+1),veneer,page));
    assert(code[0]==words[0]&&code[2]==words[2]&&code[3]==words[3]);
    assert(!frame_sv_test_patch((uintptr_t)(code+1),veneer,page)); /* reject repeated patch */
    ctx.path=code;assert(!frame_sv_abi_test(&vtable,&ctx,ctx.node+192,ctx.node,mock_upload,ctx.path));
    munmap(code,page);munmap(veneer,page);
    /* Unsupported renderer / RGB mode must preserve the original pointer. */
    ctx.path=frame_sv_test_entry();ctx.identity=1;memcpy(ctx.expected,ctx.node+192,528);ctx.node[839]=0;
    assert(!frame_sv_abi_test(&vtable,&ctx,ctx.node+192,ctx.node,mock_upload,ctx.path));ctx.node[839]=1;
    frame_sv_test_bind(mock_upload,vtable+1);
    assert(!frame_sv_abi_test(&vtable,&ctx,ctx.node+192,ctx.node,mock_upload,ctx.path));
    frame_sv_test_bind(mock_upload,vtable);
    puts("PASS: native AArch64 x19-x29, d8-d15, SP and LR return; exact default pointer/bytes; source immutable; nested scratch lifetime; 4 threads x10000; actual 4-byte BL/veneer on synthetic RX host; repeated patch/RGB/unsupported vtable bypass");
    return 0;
}
