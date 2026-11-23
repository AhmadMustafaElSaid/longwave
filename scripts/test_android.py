"""Use an isolated Android emulator and stock Chrome to save and verify a file."""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path


def adb(*args, text=True):
    return subprocess.check_output(["adb", "-e", *args], text=text, timeout=35)


def tree():
    adb("shell","uiautomator","dump","/sdcard/longwave-ui.xml")
    return ET.fromstring(adb("exec-out","cat","/sdcard/longwave-ui.xml"))


def label(node):
    return node.get("text") or node.get("content-desc") or ""


def tap(node):
    left, top, right, bottom = map(int,re.findall(r"\d+",node.attrib["bounds"]))
    adb("shell","input","tap",str((left+right)//2),str((top+bottom)//2))


def wait_node(predicate, seconds=55):
    end = time.monotonic()+seconds
    while time.monotonic()<end:
        ui = tree()
        for node in ui.iter("node"):
            if predicate(node):
                return node
        for node in ui.iter("node"):
            if label(node).lower() in {"use without an account","use chrome without an account","continue without an account","no thanks","got it"}:
                tap(node)
                break
        else:
            # Scroll a visible page before trying the next accessibility snapshot.
            scrollable = next((n for n in ui.iter("node") if n.get("scrollable")=="true"),None)
            if scrollable is not None:
                x1,y1,x2,y2 = map(int,re.findall(r"\d+",scrollable.attrib["bounds"]))
                x=(x1+x2)//2
                adb("shell","input","swipe",str(x),str(y1+(y2-y1)*3//4),str(x),str(y1+(y2-y1)//3),"350")
        time.sleep(.4)
    visible = [label(n)[:65] for n in ui.iter("node") if label(n)]
    raise RuntimeError("Expected Android control missing. Visible labels: "+str(visible))


def main():
    if "emulator-" not in adb("get-serialno"):
        raise RuntimeError("Run this check in a disposable Android emulator.")
    print(adb("shell","getprop","ro.build.version.release").strip(), "Android", flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        flags=Path(tmp)/"chrome-command-line"
        flags.write_text("chrome --no-first-run --disable-fre --no-default-browser-check\n")
        adb("push",str(flags),"/data/local/tmp/chrome-command-line")
    adb("shell","am","set-debug-app","--persistent","com.android.chrome")
    adb("shell","am","force-stop","com.android.chrome")
    with subprocess.Popen([sys.executable,"scripts/phone_fixture.py"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True) as server:
        try:
            fixture=json.loads(server.stdout.readline())
            port=fixture["origin"].rsplit(":",1)[1]
            adb("reverse","tcp:"+port,"tcp:"+port)
            adb("shell","am","start","-W","-a","android.intent.action.VIEW","-d",fixture["origin"],"com.android.chrome")
            field=wait_node(lambda n:n.get("class")=="android.widget.EditText" and not any(k in n.get("resource-id","") for k in ("url_bar","search_box")))
            tap(field)
            adb("shell","input","text",fixture["code"])
            adb("shell","input","keyevent","66")
            # Some IMEs leave the form unsubmitted after Done.
            target=wait_node(lambda n:label(n) in ("Connect","Save to phone"))
            if label(target)=="Connect":
                tap(target)
                target=wait_node(lambda n:label(n)=="Save to phone")
            tap(target)
            path="/sdcard/Download/Longwave test.wav"
            end=time.monotonic()+50
            while time.monotonic()<end:
                result=subprocess.run(["adb","-e","exec-out","cat",path.replace(" ","\\ ")],capture_output=True,timeout=10)
                if result.returncode==0 and hashlib.sha256(result.stdout).hexdigest()==fixture["sha256"]:
                    print("Android Chrome paired and saved a byte-identical file in the system Downloads directory.")
                    return
                for node in tree().iter("node"):
                    if label(node).lower() in {"download","download again","allow","continue"}:
                        tap(node)
                        break
                time.sleep(.5)
            raise RuntimeError("Android Downloads did not contain the expected file.")
        finally:
            server.stdin.close()
            server.wait(timeout=10)
            adb("shell","am","clear-debug-app")


if __name__=="__main__":
    main()
