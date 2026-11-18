"""Run a private, offline ComfyUI process only for an explicit render or CPU smoke test."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib import error, request
import uuid


class LocalEngine:
    def __init__(self, child, port, inputs, outputs, log):
        self.child, self.inputs, self.outputs, self.log = child, inputs, outputs, log
        self.address = f"http://127.0.0.1:{port}"
        class LocalOnly(request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        self.client = request.build_opener(request.ProxyHandler({}),LocalOnly())

    def api(self, path, payload=None):
        if self.child.poll() is not None:
            raise RuntimeError("The private inference process ended. See "+str(self.log))
        body = json.dumps(payload).encode() if payload is not None else None
        req = request.Request(self.address+path, data=body, headers={"Content-Type":"application/json"})
        try:
            with self.client.open(req,timeout=30) as response:
                return json.load(response)
        except error.HTTPError as exc:
            raise RuntimeError(f"Local ComfyUI HTTP {exc.code}: "+exc.read(5000).decode(errors="replace")) from exc

    def run(self, graph, outputs):
        ticket = self.api("/prompt", {"prompt":graph,"client_id":str(uuid.uuid4())})
        job = ticket["prompt_id"]
        print(f"Local ComfyUI job {job}",flush=True)
        while True:
            history = self.api("/history/"+job).get(job)
            if history:
                if history.get("status",{}).get("status_str")=="error":
                    errors = [m[1] for m in history["status"]["messages"] if m[0] in ("execution_error","execution_interrupted")]
                    detail = errors[-1] if errors else {}
                    raise RuntimeError(f"{detail.get('node_type','ComfyUI')}: {detail.get('exception_message','Job interrupted')}. Log: {self.log}")
                found = {}
                for node, label in outputs.items():
                    data = history.get("outputs",{}).get(node,{})
                    entries = data.get("images") or data.get("videos") or []
                    if not entries:
                        raise RuntimeError(f"Missing output {label} from local job {job}")
                    entry = entries[0]
                    result = (self.outputs/entry.get("subfolder","")/entry["filename"]).resolve()
                    if entry.get("type")!="output" or not result.is_relative_to(self.outputs.resolve()) or not result.is_file():
                        raise RuntimeError(f"Invalid output path for {label}")
                    found[label] = result
                return found
            time.sleep(1)


@contextmanager
def private_engine(machine, models, job, scratch, cpu=False, *, node_directory=None, extensions=()):
    engine = Path(machine["comfy_directory"]).resolve()
    python = Path(machine["python"]).resolve()
    run = scratch/("engine-"+uuid.uuid4().hex)
    inputs, outputs = run/"input", run/"output"
    inputs.mkdir(parents=True)
    outputs.mkdir()
    def link(source, target):
        try:
            os.link(source,target)
        except OSError:
            shutil.copyfile(source,target)
    for p in (job/"input").iterdir():
        link(p, inputs/p.name)
    marker = "session-"+uuid.uuid4().hex+".png"
    # The marker identifies this process's input directory, even on a text-only first job.
    from PIL import Image
    Image.new("RGB",(1,1)).save(inputs/marker)
    model_paths = run/"model-paths.yaml"
    config = {"base_path":str(models),**{p.name:p.name for p in models.iterdir() if p.is_dir()}}
    if node_directory is not None:
        (run/"custom_nodes").mkdir()
        config["custom_nodes"] = str(node_directory.resolve())
    model_paths.write_text(json.dumps({"takefive":config}), encoding="utf-8")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        port = sock.getsockname()[1]
    env = dict(os.environ,HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",HF_HUB_DISABLE_TELEMETRY="1",
               PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", TORCH_HOME=str(run/"torch"))
    flags = ["--lowvram","--reserve-vram","1.0"]
    if cpu:
        env.update(CUDA_VISIBLE_DEVICES="-1",HIP_VISIBLE_DEVICES="-1",ROCR_VISIBLE_DEVICES="-1")
        flags = ["--cpu","--disable-xformers","--disable-dynamic-vram"]
    if extensions:
        flags.extend(["--whitelist-custom-nodes", *extensions])
    args = [str(python),"-B",str(engine/"main.py"),"--listen","127.0.0.1","--port",str(port),"--offline",
            "--disable-all-custom-nodes","--disable-auto-launch","--preview-method","none","--cache-none",
            "--base-directory",str(run),"--input-directory",str(inputs),"--output-directory",str(outputs),
            "--extra-model-paths-config",str(model_paths),"--database-url","sqlite:///:memory:",*flags]
    log = scratch/(run.name+".log")
    with log.open("wb") as stream:
        # Windows GPU helpers can briefly retain their inherited working directory.
        child = subprocess.Popen(args,cwd=scratch,env=env,stdout=stream,stderr=subprocess.STDOUT,
                                 creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        try:
            local = LocalEngine(child,port,inputs,outputs,log)
            for _ in range(180):
                try:
                    meta = local.api("/object_info/LoadImage")
                    if marker in json.dumps(meta["LoadImage"]["input"]):
                        break
                except (OSError, KeyError):
                    pass
                time.sleep(1)
            else:
                raise TimeoutError("The private ComfyUI process did not become ready. See "+str(log))
            yield local
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            if run.is_dir() and run.resolve().parent==scratch.resolve():
                for delay in (0, .25, 1):
                    time.sleep(delay)
                    try:
                        shutil.rmtree(run)
                        break
                    except FileNotFoundError:
                        break
                    except OSError as exc:
                        if getattr(exc, "winerror", None) not in (32, 33):
                            raise
                else:
                    print(f"Windows is still releasing temporary render files in {run}", file=sys.stderr)
