// Development-only UI preview. This shim is NEVER copied into the extension.
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { resolve, sep, extname } from "node:path";
const root = resolve("dist/chromium");
const shim = `<script>
window.chrome={storage:{local:{get:async()=>({}),set:async()=>{}}},runtime:{sendMessage:async(message)=>{
 if(message.command==='snapshot')return {ok:true,data:{version:'UI preview',protocol:1,tools:{extractor:false,ffmpeg:false,ffprobe:false},outputDir:'UI preview — no real downloads',jobs:[]}};
 return {ok:false,error:{message:'UI preview only. Use the installed extension for downloads.'}};
}}};
document.addEventListener('DOMContentLoaded',()=>{document.title='Longwave — UI preview (simulated connection)';});
</script>`;
createServer(async (request, response) => {
  try {
    const pathname = new URL(request.url, "http://localhost").pathname;
    const file = resolve(root, "." + (pathname === "/" ? "/index.html" : pathname));
    if (!file.startsWith(root + sep)) {
      response.writeHead(403).end();
      return;
    }
    let body = await readFile(file);
    const type = extname(file);
    if (type === ".html")
      body = Buffer.from(
        body.toString().replace('<script type="module"', shim + '<script type="module"'),
      );
    response.writeHead(200, {
      "Content-Type":
        {
          ".html": "text/html; charset=utf-8",
          ".js": "text/javascript",
          ".css": "text/css",
          ".png": "image/png",
        }[type] ?? "application/octet-stream",
      "Cache-Control": "no-store",
    });
    response.end(body);
  } catch {
    response.writeHead(404).end("Not found");
  }
}).listen(4173, "127.0.0.1", () =>
  console.log("UI preview: http://127.0.0.1:4173 (no real download commands)"),
);
