#include <stddef.h>
#include <stdint.h>
#include <string.h>
typedef void (*Proc)(void);
typedef struct {uint32_t type;const void* next;uint32_t flags;size_t size;const uint32_t* code;} Info;
static size_t last_size;static int failure;
size_t mock_shader_size(void){return last_size;}
void mock_shader_failure(int value){failure=value;}
int vkCreateShaderModule(void* d,const Info* info,const void* a,uint64_t* m){(void)d;(void)a;last_size=info->size;*m=42;return failure;}
Proc vkGetDeviceProcAddr(void* d,const char* name){(void)d;return !strcmp(name,"vkCreateShaderModule")?(Proc)vkCreateShaderModule:0;}
Proc vkGetInstanceProcAddr(void* i,const char* name){(void)i;if(!strcmp(name,"vkGetDeviceProcAddr"))return (Proc)vkGetDeviceProcAddr;return vkGetDeviceProcAddr(i,name);}
