#pragma once
#include <cerrno>
#include <cmath>
#include <cstdlib>
inline bool parse_hue(const char *text,float &value){
 if(!text||!*text)return false;
 char *end=nullptr;errno=0;value=std::strtof(text,&end);
 return end!=text&&!*end&&!errno&&std::isfinite(value)&&value>=0&&value<=1;
}
