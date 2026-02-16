HOST=$1
PORT=$2

vllm serve Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8 \
  --dtype auto \
  --port $PORT \
  --host $HOST \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_xml \
  --enable-chunked-prefill \
  --async-scheduling \