HOST=$1
PORT=$2

vllm serve openai/gpt-oss-120b \
  --dtype auto \
  --port $PORT \
  --host $HOST \
  --config local_lms/gpt_oss.yaml \