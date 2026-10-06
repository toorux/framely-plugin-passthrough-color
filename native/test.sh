#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
mkdir -p build
cc -std=c11 -O2 -Wall -Wextra -Werror -pthread -DFRAME_SV_TEST -fPIC -shared frame_sv_module.c frame_sv_uniform.c frame_color_uniform.c frame_color_shader.c frame_sv_entry.S -ldl -lm -o build/libframe_sv_test.so
cc -O2 -fPIC -shared frame_sv_uniform.c -lm -o build/libframe_sv_uniform.so
cc -std=c11 -O2 -Wall -Wextra -Werror -pthread tests/native_test.c tests/abi_test.S -Lbuild -lframe_sv_test '-Wl,-rpath,$ORIGIN' -lm -o build/frame_sv_native_test
build/frame_sv_native_test
cc -std=c11 -O2 -Wall -Wextra -Werror -fPIC -shared tests/vulkan_mock.c -o build/libvulkan_mock.so
python3 tests/test_color.py
python3 tests/test_uniform.py
python3 tests/test_module.py
