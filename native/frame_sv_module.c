#define _GNU_SOURCE
#include <ctype.h>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <link.h>
#include <math.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

/* Framely startup module. Constructor is opt-in; never attaches to a process.
 * No OpenVR calls, camera access, UI writes, GPU capture or disk binary patch.
 */
typedef void (*Upload)(void *, void *, const void *);
extern void frame_sv_entry(void);
extern int frame_sv_prepare(void *, const void *, int, float, float);
static _Atomic uint64_t cached = UINT64_C(0x3f8000003f800000);
static _Atomic int stopping;
static _Atomic uint64_t uploads, matched_mono, matched_rgb, unmatched;
static pthread_t reader;
static int reader_started;
static const char *control_file = "/run/user/1000/frame-sv-test/settings.json";
static uintptr_t expected_upload, expected_vtable;
static _Thread_local unsigned inside __attribute__((tls_model("initial-exec")));
_Static_assert(__atomic_always_lock_free(8, 0), "cache must be lock-free");

static uint64_t pack(float s, float v) {
    uint32_t a,b; memcpy(&a,&s,4); memcpy(&b,&v,4);
    return (uint64_t)a | ((uint64_t)b << 32);
}
/* Strict, bounded test-control JSON. A CEF/OpenVR bridge is not implemented. */
static const char *ws(const char *p) { while (*p && isspace((unsigned char)*p)) ++p; return p; }
static int parse_control(const char *p, uint64_t *result) {
    float s=1,v=1; unsigned seen=0;
    p=ws(p); if (*p++!='{') return 0; p=ws(p);
    while (*p!='}') {
        unsigned bit; float *dst;
        if (!strncmp(p,"\"saturation\"",12)) { bit=1; dst=&s; p+=12; }
        else if (!strncmp(p,"\"brightness\"",12)) { bit=2; dst=&v; p+=12; }
        else return 0;
        if (seen&bit) return 0;
        seen|=bit;
        p=ws(p); if (*p++!=':') return 0; p=ws(p);
        const char *begin=p;
        if (*p=='-') ++p;
        if (*p=='0') ++p;
        else { if (*p<'1'||*p>'9') return 0; while (isdigit((unsigned char)*p)) ++p; }
        if (*p=='.') { ++p; if (!isdigit((unsigned char)*p)) return 0; while (isdigit((unsigned char)*p)) ++p; }
        if (*p=='e'||*p=='E') { ++p; if (*p=='+'||*p=='-') ++p; if (!isdigit((unsigned char)*p)) return 0; while (isdigit((unsigned char)*p)) ++p; }
        char *end; errno=0; *dst=strtof(begin,&end);
        if (end!=p||errno||!isfinite(*dst)) return 0;
        p=ws(p); if (*p=='}') break;
        if (*p++!=',') return 0;
        p=ws(p); if (*p=='}') return 0;
    }
    p=ws(p+1); if (*p) return 0;
    if (s<0||s>1||v<.25f||v>1.5f) return 0;
    *result=pack(s,v); return 1;
}
static uint64_t read_control(void) {
    const uint64_t identity=UINT64_C(0x3f8000003f800000);
    char text[257]; struct stat st;
    int fd=open(control_file,O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);
    if (fd<0) return identity;
    if (fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_uid!=geteuid()||st.st_size<2||st.st_size>256) { close(fd); return identity; }
    ssize_t count=read(fd,text,sizeof(text)-1); close(fd);
    if (count!=st.st_size||memchr(text,0,(size_t)count)) return identity;
    text[count]=0; uint64_t value;
    return parse_control(text,&value)?value:identity;
}
static void publish_status(void){
 const char *path=getenv("FRAME_SV_STATUS_FILE");if(!path||path[0]!='/'||strlen(path)>4000)return;
 char temporary[4096],json[512];snprintf(temporary,sizeof(temporary),"%s.%ld.tmp",path,(long)getpid());
 int n=snprintf(json,sizeof(json),"{\"pid\":%ld,\"active\":true,\"matchedMono\":%llu,\"matchedRgb\":%llu}\n",(long)getpid(),(unsigned long long)atomic_load_explicit(&matched_mono,memory_order_relaxed),(unsigned long long)atomic_load_explicit(&matched_rgb,memory_order_relaxed));
 int fd=open(temporary,O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK,0600);if(fd<0)return;struct stat st;
 int ok=!fstat(fd,&st)&&S_ISREG(st.st_mode)&&st.st_uid==geteuid()&&write(fd,json,(size_t)n)==n;close(fd);if(ok)rename(temporary,path);else unlink(temporary);
}
static void *read_loop(void *unused) {
    (void)unused;
    unsigned polls=0;
    while (!atomic_load_explicit(&stopping,memory_order_relaxed)) {
        atomic_store_explicit(&cached,read_control(),memory_order_relaxed);
        if(++polls%4==0)publish_status();
        if (polls==4 || polls%40==0) {
            uint64_t current=atomic_load_explicit(&cached,memory_order_relaxed);
            uint32_t a=(uint32_t)current,b=(uint32_t)(current>>32);float s,v;
            memcpy(&s,&a,4);memcpy(&v,&b,4);
            fprintf(stderr,"frame-sv: status uploads=%llu matched_mono=%llu matched_rgb=%llu unmatched=%llu S=%.3f V=%.3f\n",
                    (unsigned long long)atomic_load_explicit(&uploads,memory_order_relaxed),
                    (unsigned long long)atomic_load_explicit(&matched_mono,memory_order_relaxed),
                    (unsigned long long)atomic_load_explicit(&matched_rgb,memory_order_relaxed),
                    (unsigned long long)atomic_load_explicit(&unmatched,memory_order_relaxed),s,v);
        }
        struct timespec delay={0,250000000}; nanosleep(&delay,0);
    }
    return 0;
}
static int start_reader(void) {
    atomic_store(&stopping,0);
    if (pthread_create(&reader,0,read_loop,0)) return 0;
    reader_started=1; return 1;
}
static void stop_reader(void) {
    if (reader_started) { atomic_store(&stopping,1); pthread_join(reader,0); reader_started=0; }
}

__attribute__((visibility("hidden")))
void frame_sv_upload(void *iface,void *buffer,const void *original,
                     const unsigned char *node,Upload call) {
    uint64_t value=atomic_load_explicit(&cached,memory_order_relaxed);
    int known=(uintptr_t)call==expected_upload && iface && node &&
        (uintptr_t)original==(uintptr_t)node+192 &&
        *(const uintptr_t *)iface==expected_vtable;
    int mono=known && node[839];
    atomic_fetch_add_explicit(&uploads,1,memory_order_relaxed);
    atomic_fetch_add_explicit(known?(mono?&matched_mono:&matched_rgb):&unmatched,1,memory_order_relaxed);
    if (value==UINT64_C(0x3f8000003f800000)||inside||!mono) {
        call(iface,buffer,original); return;
    }
    float s,v; uint32_t a=(uint32_t)value,b=(uint32_t)(value>>32);
    memcpy(&s,&a,4); memcpy(&v,&b,4);
    _Alignas(16) unsigned char scratch[528];
    frame_sv_prepare(scratch,original,1,s,v);
    ++inside;
    /* Guarded CFacetVRRenderer upload copies bytes in both normal paths.
     * The scratch remains alive through the original synchronous call.
     */
    call(iface,buffer,scratch);
    --inside;
}

/* SHA-256 is computed here to avoid new shared-library dependencies. */
static uint32_t rr(uint32_t x,unsigned n) { return (x>>n)|(x<<(32-n)); }
static void sha_block(uint32_t h[8], const unsigned char in[64]) {
    static const uint32_t k[64]={
      0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
      0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
      0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
      0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
      0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
      0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
      0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
      0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
    uint32_t w[64]; for(unsigned i=0;i<16;++i) w[i]=(uint32_t)in[4*i]<<24|(uint32_t)in[4*i+1]<<16|(uint32_t)in[4*i+2]<<8|in[4*i+3];
    for(unsigned i=16;i<64;++i) w[i]=w[i-16]+(rr(w[i-15],7)^rr(w[i-15],18)^(w[i-15]>>3))+w[i-7]+(rr(w[i-2],17)^rr(w[i-2],19)^(w[i-2]>>10));
    uint32_t a=h[0],b=h[1],c=h[2],d=h[3],e=h[4],f=h[5],g=h[6],z=h[7];
    for(unsigned i=0;i<64;++i) { uint32_t t=z+(rr(e,6)^rr(e,11)^rr(e,25))+((e&f)^(~e&g))+k[i]+w[i]; uint32_t u=(rr(a,2)^rr(a,13)^rr(a,22))+((a&b)^(a&c)^(b&c)); z=g;g=f;f=e;e=d+t;d=c;c=b;b=a;a=t+u; }
    h[0]+=a;h[1]+=b;h[2]+=c;h[3]+=d;h[4]+=e;h[5]+=f;h[6]+=g;h[7]+=z;
}
__attribute__((noinline)) static int hash_fd(int fd,unsigned char out[32]) {
    uint32_t h[8]={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    unsigned char buf[64]; size_t used=0; uint64_t total=0;
    for (;;) {
        ssize_t n=read(fd,buf+used,64-used);
        if (n<0) { if(errno==EINTR) continue; return 0; }
        if(!n) break;
        used+=(size_t)n; total+=(uint64_t)n;
        if(used==64) { sha_block(h,buf);used=0; }
    }
    buf[used++]=128;
    if(used>56) { memset(buf+used,0,64-used);sha_block(h,buf);used=0; }
    memset(buf+used,0,56-used); total*=8;
    for(unsigned i=0;i<8;++i) buf[63-i]=(unsigned char)(total>>(8*i));
    sha_block(h,buf);
    for(unsigned i=0;i<8;++i) for(unsigned j=0;j<4;++j) out[4*i+j]=(unsigned char)(h[i]>>(24-8*j));
    return 1;
}
typedef struct { unsigned char hash[32];uintptr_t context,site,upload,vtable; } Profile;
static const Profile profiles[]={
 { {0xab,0x33,0xd3,0x2b,0x15,0xf5,0x5d,0x35,0x6d,0x6c,0x45,0x09,0xb6,0x35,0xfa,0xc6,0xdc,0xa9,0x61,0x4e,0x64,0x85,0x22,0x6e,0x75,0xb6,0x2a,0xaa,0xa3,0xaa,0x63,0x9e},0x167ab0,0x167ad4,0x2a27c0,0x5aab10 },
 { {0xd7,0x5d,0x3a,0x0d,0x3a,0x86,0xf8,0x75,0x0e,0x8f,0x77,0xfd,0x43,0x57,0x56,0x05,0x46,0x5c,0x8f,0xa2,0xbe,0xf9,0x73,0xa7,0x59,0x7c,0x4a,0x1c,0x8c,0xb1,0x23,0xb3},0x166d48,0x166d6c,0x2a1af8,0x5a7b10 }
};
static const Profile *profile_for(const unsigned char *hash){for(size_t i=0;i<sizeof(profiles)/sizeof(profiles[0]);++i)if(!memcmp(hash,profiles[i].hash,32))return &profiles[i];return 0;}
static const unsigned char upload_context[]={0xe0,0xbb,0x40,0xbd,0x62,0x03,0x03,0x91,0xe1,0x43,0x41,0xbd,0x60,0x07,0x40,0xf9,0x08,0x08,0x21,0x1e,0x61,0x6b,0x41,0xf9,0x68,0xff,0x01,0xbd,0x07,0x00,0x40,0xf9,0xe7,0x3c,0x40,0xf9,0xe0,0x00,0x3f,0xd6};
static int match_context(const void *memory) { return !memcmp(memory,upload_context,sizeof(upload_context)); }
static int main_base(struct dl_phdr_info *info,size_t size,void *out) {
    (void)size; if (info->dlpi_name&&*info->dlpi_name) return 0;
    *(uintptr_t *)out=info->dlpi_addr; return 1;
}
static void *make_veneer(uintptr_t site,size_t page) {
    uintptr_t anchor=site&~(uintptr_t)(page-1);
    for(uintptr_t distance=page;distance<UINT64_C(0x07ff0000);distance+=page*16) {
        for(unsigned side=0;side<2;++side) {
            uintptr_t address=side?anchor-distance:anchor+distance;
            void *p=mmap((void *)address,page,PROT_READ|PROT_WRITE,
                         MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);
            if(p==MAP_FAILED) continue;
            if((uintptr_t)p!=address) { munmap(p,page);continue; }
            uint32_t instructions[2]={0x58000050,0xd61f0200};
            memcpy(p,instructions,8); uintptr_t dest=(uintptr_t)frame_sv_entry; memcpy((char *)p+8,&dest,8);
            __builtin___clear_cache(p,(char *)p+16);
            if(mprotect(p,page,PROT_READ|PROT_EXEC)) { munmap(p,page);return 0; }
            return p;
        }
    }
    return 0;
}
static int patch_site(uintptr_t site,void *veneer,size_t page) {
    intptr_t distance=(intptr_t)veneer-(intptr_t)site;
    if ((distance&3)||distance<-(INT64_C(1)<<27)||distance>=(INT64_C(1)<<27)) return 0;
    if (__atomic_load_n((uint32_t *)site,__ATOMIC_ACQUIRE)!=0xd63f00e0) return 0;
    uintptr_t region=site&~((uintptr_t)page-1);
    if(mprotect((void *)region,page,PROT_READ|PROT_WRITE)) return 0;
    uint32_t opcode=0x94000000|((uint32_t)(distance/4)&0x03ffffff);
    __atomic_store_n((uint32_t *)site,opcode,__ATOMIC_RELEASE);
    __builtin___clear_cache((char *)site,(char *)site+4);
    if(mprotect((void *)region,page,PROT_READ|PROT_EXEC)) _exit(125);
    return 1;
}
__attribute__((constructor)) static void initialize(void) {
    const char *enable=getenv("FRAME_SV_ENABLE"); if(!enable||strcmp(enable,"1")) return;
    char executable[4096]; ssize_t n=readlink("/proc/self/exe",executable,sizeof(executable)-1);
    if(n<0) return;
    executable[n]=0;
    const char *name=strrchr(executable,'/');
    if(!name||strcmp(name+1,"vrcompositor")) return;
    int fd=open("/proc/self/exe",O_RDONLY|O_CLOEXEC); unsigned char digest[32];
    if(fd<0) return;
    int valid=hash_fd(fd,digest); close(fd);
    const Profile *profile=valid?profile_for(digest):0;
    if(!profile) { fputs("frame-sv: executable hash rejected; inactive\n",stderr);return; }
    uintptr_t base=0; dl_iterate_phdr(main_base,&base);
    if(!base||!match_context((void *)(base+profile->context))||*(uintptr_t *)(base+profile->vtable+120)!=base+profile->upload) { fputs("frame-sv: instruction/vtable rejected; inactive\n",stderr);return; }
    const char *path=getenv("FRAME_SV_CONTROL_FILE");if(!path||path[0]!='/'||strlen(path)>4000){fputs("frame-sv: control path missing; inactive\n",stderr);return;}control_file=path;
    long page=sysconf(_SC_PAGESIZE); if(page<=0) return;
    void *veneer=make_veneer(base+profile->site,(size_t)page); if(!veneer) return;
    expected_upload=base+profile->upload; expected_vtable=base+profile->vtable;
    if(!start_reader()) { munmap(veneer,(size_t)page);return; }
    if(!patch_site(base+profile->site,veneer,(size_t)page)) { stop_reader();munmap(veneer,(size_t)page);return; }
    fputs("frame-sv: guarded startup hook active; default passthrough; control reader only\n",stderr);
}
__attribute__((destructor)) static void finalize(void) { stop_reader(); }

#ifdef FRAME_SV_TEST
void frame_sv_test_bind(Upload fn,uintptr_t vtable) { expected_upload=(uintptr_t)fn;expected_vtable=vtable; }
void frame_sv_test_publish(float s,float v) { atomic_store(&cached,pack(s,v)); }
int frame_sv_test_parse(const char *s,uint64_t *out) { return parse_control(s,out); }
int frame_sv_test_hash(const char *path,unsigned char *out) { int fd=open(path,O_RDONLY);if(fd<0)return 0;int ok=hash_fd(fd,out);close(fd);return ok; }
int frame_sv_test_accept_file(const char *path) { unsigned char digest[32];int fd=open(path,O_RDONLY);if(fd<0)return 0;int ok=hash_fd(fd,digest);close(fd);return ok&&profile_for(digest)!=0; }
int frame_sv_test_context(const void *data) { return match_context(data); }
int frame_sv_test_reader(const char *path) { control_file=path;return start_reader(); }
void frame_sv_test_stop(void) { stop_reader(); }
uint64_t frame_sv_test_cache(void) { return atomic_load(&cached); }
void *frame_sv_test_veneer(uintptr_t site,size_t page) { return make_veneer(site,page); }
int frame_sv_test_patch(uintptr_t site,void *veneer,size_t page) { return patch_site(site,veneer,page); }
void *frame_sv_test_entry(void) { return (void *)frame_sv_entry; }
#endif
