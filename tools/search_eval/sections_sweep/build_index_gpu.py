"""Build the meaning index with this checkout's own indexer (python retrieval.py), with the model run on an NVIDIA GPU.

    set LASTBOOK_DATA=<a data folder whose derived/index you can rebuild>
    python -B tools/search_eval/sections_sweep/build_index_gpu.py <folder holding onnxruntime-gpu and its CUDA wheels>

The only change from a plain `python retrieval.py` is that onnxruntime is imported from the given folder
(`pip install --target <folder> onnxruntime-gpu nvidia-cuda-runtime nvidia-cudnn-cu13 nvidia-cublas ...`, so the
global onnxruntime is untouched) and the embedder's session asks for CUDAExecutionProvider first. No file of the
checkout is edited. Used for the "index built by this part's own indexer" check in docs/TRIAGE-SEARCH.md §1.
"""
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, os.path.abspath(sys.argv[1]))
sys.path.insert(1, str(ROOT))
os.environ['ORT_DISABLE_TELEMETRY'] = '1'
if os.name == 'nt':  # as retrieval.py does, before onnxruntime is imported
    from engine import quiet_onnx
    quiet_onnx.silence()
import onnxruntime as ort  # noqa: E402

ort.preload_dlls()
_Session = ort.InferenceSession


def gpu_session(path, so=None, providers=None, **kw):
    return _Session(path, so, providers=['CUDAExecutionProvider', 'CPUExecutionProvider'], **kw)


ort.InferenceSession = gpu_session
os.chdir(ROOT)
sys.argv = ['retrieval.py']
print('onnxruntime', ort.__version__, ort.get_available_providers(), flush=True)
runpy.run_path(str(ROOT / 'retrieval.py'), run_name='__main__')
