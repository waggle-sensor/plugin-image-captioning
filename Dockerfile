# Use a lightweight Python base image
FROM waggle/plugin-base:1.1.1-base

RUN apt-get update \
  && apt-get install -y \
  wget \
  curl

COPY requirements.txt /app/
RUN pip3 install -r /app/requirements.txt

# Using huggingface-cli to download the Florence2 model
# --local-dir disables the caching in huggingface-cli to place
# actual files in the --local-dir, not in $HOME/.cache/huggingface
# Also, we pin the commit that was on July 20, 2024
RUN huggingface-cli download \
  --local-dir /app/Florence-2-base \
  --revision ee1f1f163f352801f3b7af6b2b96e4baaa6ff2ff \
  microsoft/Florence-2-base

COPY app.py flash_attn.py icon.png /app/
WORKDIR /app
ENTRYPOINT ["python3", "-u", "/app/app-cpu.py"]