git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp

cmake -B build -G Ninja \
  -DGGML_VULKAN=ON \
  -DGGML_NATIVE=ON \
  -DLLAMA_CURL=ON \
  -DCMAKE_BUILD_TYPE=Release

cmake --build build --config Release -j $(nproc)