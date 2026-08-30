FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

# Install torch from the CUDA 12.1 wheel index before the rest, so SigLIP can run
# on the GPU. cu121 is forward-compatible with newer drivers; only the driver has
# to be >= the wheel's CUDA version, and the container brings its own CUDA
# runtime, so no CUDA toolkit is needed on the host.
# Swap this index for .../whl/cpu to get the ~200MB CPU-only build back.
# The -r install below then sees torch as satisfied and leaves it alone.
RUN pip install --no-cache-dir --default-timeout=900 --retries=10 \
    --index-url https://download.pytorch.org/whl/cu121 \
    torch==2.2.2

RUN pip install --no-cache-dir --default-timeout=600 --retries=10 -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
