"""Timed 4/7/10-hour generated-media transfers through the real job process."""
import argparse
import functools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
from longwave.store import Store


class QuietFiles(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def tree_rss_kib(pid):
    if not sys.platform.startswith("linux"):
        return None
    total, pending = 0, [pid]
    while pending:
        current = pending.pop()
        try:
            base = Path("/proc") / str(current)
            for line in (base / "status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    total += int(line.split()[1])
            for tasks in (base / "task").iterdir():
                pending.extend(map(int, (tasks / "children").read_text().split()))
        except (FileNotFoundError, ProcessLookupError):
            continue
    return total


def measure(hours, root, port, ffmpeg, ffprobe):
    location = root / ("case-" + str(hours))
    location.mkdir()
    duration = hours * 3600
    source = location / "generated.mp3"
    media = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error"]
    subprocess.run([*media,"-stream_loop","-1","-i",str(root / "seed.mp3"),"-t",str(duration),
                    "-c:a","copy",str(source)],check=True)
    journal = Store(location / "journal")
    (journal.root / "config.json").write_text(json.dumps(dict(output_dir=str(location / "out"),ffmpeg=ffmpeg,ffprobe=ffprobe)))
    url = "https://soundcloud.com/fixture/long-recording"
    fmt = dict(format_id="fixture",ext="mp3",protocol="http",url=f"http://127.0.0.1:{port}/{location.name}/generated.mp3",
               acodec="mp3",vcodec="none",abr=24,filesize=source.stat().st_size)
    (journal.root / "fixture-info.json").write_text(json.dumps(dict(id="long",title="Generated recording",uploader="Longwave",
        duration=duration,downloadable=False,formats=[fmt],extractor="fixture",webpage_url=url)))
    job = journal.create(str(uuid.uuid4()), url, "original")
    started = time.monotonic()
    with subprocess.Popen([sys.executable,str(ROOT / "companion/tests/fixture_job.py"),str(journal.root),job["id"]]) as proc:
        peak = None
        while proc.poll() is None:
            sample = tree_rss_kib(proc.pid)
            if sample is not None:
                peak = max(peak or 0,sample)
            time.sleep(.05)
        if proc.returncode:
            raise RuntimeError(f"Job process exited {proc.returncode}")
    elapsed = time.monotonic() - started
    job = journal.get(job["id"])
    if job["state"] != "completed":
        raise RuntimeError(str(job["error"]))
    output = Path(job["output"])
    def probe(file):
        result = subprocess.check_output([ffprobe,"-v","error","-show_entries","format=duration","-of","csv=p=0",str(file)])
        return float(result.strip())
    checked = probe(output)
    assert abs(checked-duration) < 3, (duration,checked)
    assert abs(checked-probe(source)) < 1
    for start in (0, duration//2, duration-5):
        subprocess.run([*media,"-xerror","-ss",str(start),"-i",str(output),"-t","3","-f","null","-"],check=True)
    return dict(hours=hours,outputSeconds=checked,outputBytes=output.stat().st_size,jobSeconds=round(elapsed,2),
                peakSampledTreeRssKiB=peak,decodedWindowsSeconds=[0,duration//2,duration-5])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    ffmpeg = os.environ.get("LONGWAVE_TEST_FFMPEG") or shutil.which("ffmpeg")
    ffprobe = os.environ.get("LONGWAVE_TEST_FFPROBE") or shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        sys.exit("Set LONGWAVE_TEST_FFMPEG and LONGWAVE_TEST_FFPROBE or install FFmpeg.")
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        subprocess.run([ffmpeg,"-nostdin","-loglevel","error","-f","lavfi","-i","sine=frequency=440:sample_rate=24000",
                        "-t","20","-ac","1","-c:a","libmp3lame","-b:a","24k",str(root / "seed.mp3")],check=True)
        with ThreadingHTTPServer(("127.0.0.1",0), functools.partial(QuietFiles,directory=str(root))) as server:
            thread = threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                results = []
                for hours in (4,7,10):
                    row = measure(hours,root,server.server_port,ffmpeg,ffprobe)
                    results.append(row)
                    print(json.dumps(row),flush=True)
            finally:
                server.shutdown()
                thread.join()
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(results,indent=2)+"\n")


if __name__ == "__main__":
    main()
