#include "frame_compat.h"
#include "frame_shapes.h"
#include <elf.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
static const unsigned char context[]={0xe0,0xbb,0x40,0xbd,0x62,0x03,0x03,0x91,0xe1,0x43,0x41,0xbd,0x60,0x07,0x40,0xf9,0x08,0x08,0x21,0x1e,0x61,0x6b,0x41,0xf9,0x68,0xff,0x01,0xbd,0x07,0x00,0x40,0xf9,0xe7,0x3c,0x40,0xf9,0xe0,0x00,0x3f,0xd6};
static int range(size_t size,uint64_t at,uint64_t n){return at<=size&&n<=size-at;}
int frame_find_profile(const char* path,FrameProfile* out){
 int fd=open(path,O_RDONLY);if(fd<0)return 0;struct stat st;
 if(fstat(fd,&st)||st.st_size<(off_t)sizeof(Elf64_Ehdr)||st.st_size>128*1024*1024){close(fd);return 0;}
 size_t size=(size_t)st.st_size;const unsigned char* data=mmap(0,size,PROT_READ,MAP_PRIVATE,fd,0);close(fd);if(data==MAP_FAILED)return 0;
 int ok=0;FrameProfile found={0};unsigned contexts=0,uploads=0,tables=0;
 const Elf64_Ehdr* h=(const void*)data;
 if(memcmp(h->e_ident,ELFMAG,4)||h->e_ident[EI_CLASS]!=ELFCLASS64||h->e_ident[EI_DATA]!=ELFDATA2LSB||h->e_machine!=EM_AARCH64||h->e_type!=ET_DYN||h->e_shentsize!=sizeof(Elf64_Shdr)||!h->e_shnum||h->e_shoff%8||!range(size,h->e_shoff,(uint64_t)h->e_shnum*sizeof(Elf64_Shdr)))goto done;
 const Elf64_Shdr* sections=(const void*)(data+h->e_shoff);
 for(unsigned j=0;j<h->e_shnum;j++){
  const Elf64_Shdr* s=sections+j;if(!range(size,s->sh_offset,s->sh_size)||s->sh_offset%4)continue;
  if(s->sh_type!=SHT_PROGBITS||(s->sh_flags&(SHF_ALLOC|SHF_EXECINSTR))!=(SHF_ALLOC|SHF_EXECINSTR))continue;
  for(size_t i=0;i+sizeof(context)+256<=s->sh_size;i+=4){
   const unsigned char* p=data+s->sh_offset+i;
   if(!memcmp(p,context,sizeof(context))){
    int mono=0;for(unsigned k=40;k<256;k+=4){uint32_t w;memcpy(&w,p+k,4);if(w==0x394d1f60)mono=1;}
    if(mono){found.context=s->sh_addr+i;found.site=found.context+36;++contexts;}
   }
  }
  for(size_t i=0;i+sizeof(upload_shape)<=s->sh_size;i+=4){
   const unsigned char* p=data+s->sh_offset+i;uint32_t first;memcpy(&first,p,4);
   if(first==upload_shape[0]&&frame_shape(p,upload_shape,sizeof(upload_shape)/4)){found.upload=s->sh_addr+i;++uploads;}
  }
 }
 if(contexts!=1||uploads!=1)goto done;
 for(unsigned j=0;j<h->e_shnum;j++){
  const Elf64_Shdr* s=sections+j;
  if(s->sh_type!=SHT_RELA||s->sh_entsize!=sizeof(Elf64_Rela)||s->sh_offset%8||s->sh_size%sizeof(Elf64_Rela)||!range(size,s->sh_offset,s->sh_size))continue;
  const Elf64_Rela* rs=(const void*)(data+s->sh_offset);
  for(size_t i=0;i<s->sh_size/sizeof(*rs);i++)if(ELF64_R_TYPE(rs[i].r_info)==R_AARCH64_RELATIVE&&rs[i].r_addend==(Elf64_Sxword)found.upload&&rs[i].r_offset>=120){
   uintptr_t table=rs[i].r_offset-120;
   for(unsigned k=0;k<h->e_shnum;k++){const Elf64_Shdr* t=sections+k;if((t->sh_flags&SHF_ALLOC)&&!(t->sh_flags&SHF_EXECINSTR)&&t->sh_type!=SHT_NOBITS&&table>=t->sh_addr&&table-t->sh_addr<=t->sh_size&&128<=t->sh_size-(table-t->sh_addr)){found.vtable=table;++tables;break;}}
  }
 }
 if(tables==1){*out=found;ok=1;}
 done:munmap((void*)data,size);return ok;
}
int frame_sv_probe_file(const char* path){FrameProfile p;return frame_find_profile(path,&p);}
#ifdef FRAME_SV_TEST
int frame_test_camera_shape(const void* data,size_t bytes,unsigned method){
 const uint32_t* shapes[]={visible_shape,show_shape,get_shape,set_shape};
 const size_t sizes[]={sizeof(visible_shape),sizeof(show_shape),sizeof(get_shape),sizeof(set_shape)};
 return method<4&&bytes>=sizes[method]&&frame_shape(data,shapes[method],sizes[method]/4);
}
#endif
