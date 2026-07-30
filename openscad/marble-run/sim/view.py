"""Write an assembly and a marble's trajectory out as a self-contained HTML page.

The page is one WebGL canvas: the placed pieces, the path the marble took, and the marble
moving along it. Everything is baked in -- the geometry, the trajectory, the route -- so what
you watch is the run pybullet actually produced, not a recreation of it. Nothing is fetched
and no physics runs in the browser, which is deliberate: a second engine with different
tuning would give different numbers from the ones the README quotes, and an animation that
merely looks like evidence is worse than none.

    python3 view.py            # the tower twister, to /tmp/marble-run-view.html
"""
import base64
import json
import pathlib
import sys

import numpy as np
import trimesh

import run as runner
from assembly import MARBLE_R, Assembly, MINI_H

COLOURS = ["#c8551a", "#2f7d8c", "#7a6a5d", "#4a7d3f", "#8c6d2f"]


def _pack(mesh, budget=6000):
    """Decimate, then check the decimation kept the shape, then quantise to int16.

    Asking for a face count and trusting it is how this page once shipped a spiral ramp with
    9.4% of its volume gone and triangles slashing across it. The target is verified -- on
    volume AND on the bounding box, because volume alone passes a decimation that has eaten
    the stud: 6000 faces takes 3 mm off the ramp's and costs 0.05% of the volume, the stud
    being nearly all surface and nearly no solid.
    """
    m = mesh
    for target in (budget, budget * 2, budget * 4):
        if len(mesh.faces) <= target:
            break
        d = mesh.simplify_quadric_decimation(face_count=target)
        if (abs(d.volume - mesh.volume) / abs(mesh.volume) < 0.005
                and np.abs(d.bounds - mesh.bounds).max() < 0.2):
            m = d
            break
    v = np.asarray(m.vertices, float)
    scale = float(np.abs(v).max()) or 1.0
    return dict(
        pos=base64.b64encode(np.round(v / scale * 32767).astype("<i2").tobytes()).decode(),
        idx=base64.b64encode(m.faces.astype("<u4" if len(v) > 65535 else "<u2")
                             .tobytes()).decode(),
        i32=1 if len(v) > 65535 else 0, scale=round(scale, 4), tris=int(len(m.faces)))


PAGE = """<title>marble-run / %(title)s</title>
<style>
:root{--sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
  --bg:#F6F3EF;--panel:#fff;--ink:#211D19;--muted:#77706A;--line:#E5DFD7;--accent:#D4550F;
  --stage-a:#EFEAE2;--stage-b:#DCD4C8}
@media (prefers-color-scheme:dark){:root{--bg:#141210;--panel:#1D1A16;--ink:#EFEAE3;
  --muted:#968D84;--line:#2E2A25;--accent:#F2762B;--stage-a:#22201C;--stage-b:#131110}}
:root[data-theme=dark]{--bg:#141210;--panel:#1D1A16;--ink:#EFEAE3;--muted:#968D84;
  --line:#2E2A25;--accent:#F2762B;--stage-a:#22201C;--stage-b:#131110}
:root[data-theme=light]{--bg:#F6F3EF;--panel:#fff;--ink:#211D19;--muted:#77706A;
  --line:#E5DFD7;--accent:#D4550F;--stage-a:#EFEAE2;--stage-b:#DCD4C8}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.5;font:14px/1.5 var(--sans)}
.wrap{max-width:1060px;margin:0 auto;padding:24px 20px 40px;display:flex;
  flex-direction:column;gap:16px}
h1{margin:0;font-size:21px;font-weight:620;letter-spacing:-.015em}
h1 span{color:var(--accent)}
p.sub{margin:0;color:var(--muted);max-width:64ch}
.stage{position:relative;background:var(--panel);border:1px solid var(--line);
  border-radius:11px;overflow:hidden}
canvas{display:block;width:100%%;height:clamp(320px,56vh,560px);touch-action:none;cursor:grab;
  background:radial-gradient(120%% 90%% at 50%% 8%%,var(--stage-a),var(--stage-b))}
canvas:active{cursor:grabbing}
.bar{display:flex;align-items:center;gap:12px;padding:9px 12px;border-top:1px solid var(--line)}
button{appearance:none;cursor:pointer;background:var(--accent);color:#fff;border:0;
  border-radius:7px;padding:6px 14px;font:inherit;font-weight:600}
button.ghost{background:transparent;color:var(--muted);border:1px solid var(--line)}
input[type=range]{flex:1;accent-color:var(--accent)}
code{font-family:var(--mono);font-size:12.5px}
.route{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--accent);
  border-radius:9px;padding:12px 15px}
.route b{color:var(--accent)}
.t{font-family:var(--mono);font-size:12px;color:var(--muted);min-width:8ch;text-align:right;
  font-variant-numeric:tabular-nums}
button:focus-visible,input:focus-visible,canvas:focus-visible{outline:2px solid var(--accent);
  outline-offset:2px}
</style>
<div class=wrap>
  <div>
    <h1>marble-run <span>/ %(title)s</span></h1>
    <p class=sub>%(sub)s Drag to turn, scroll to zoom. The line is the path the marble took;
    the marble runs along it at a quarter speed &mdash; the whole run is %(seconds).2f s.</p>
  </div>
  <div class=stage>
    <canvas id=cv></canvas>
    <div class=bar>
      <button id=play>Pause</button>
      <input type=range id=scrub min=0 max=%(nlast)d value=0>
      <span class=t id=clock></span>
      <button class=ghost id=reset>Reset view</button>
    </div>
  </div>
  <div class=route>Route: <b>%(route)s</b> &nbsp;·&nbsp; %(ending)s at
    <code>%(seconds).2f s</code></div>
</div>
<script>
const PIECES=%(pieces)s, PATH=%(path)s, DT=%(dt)f, COLOURS=%(colours)s;
const CENTRE=%(centre)s, DIST0=%(dist)f, SPEED=0.25, HOLD=0.6;
const b64=s=>{const b=atob(s),u=new Uint8Array(b.length);
  for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return u;};
const sub=(a,b)=>[a[0]-b[0],a[1]-b[1],a[2]-b[2]], dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const nrm=a=>{const l=Math.hypot(...a)||1;return[a[0]/l,a[1]/l,a[2]/l];};
const M4={persp(f,a,n,x){const t=1/Math.tan(f/2);
    return[t/a,0,0,0,0,t,0,0,0,0,(x+n)/(n-x),-1,0,0,2*x*n/(n-x),0];},
  mul(a,b){const o=new Array(16);for(let i=0;i<4;i++)for(let j=0;j<4;j++){let s=0;
    for(let k=0;k<4;k++)s+=a[k*4+j]*b[i*4+k];o[i*4+j]=s;}return o;},
  look(e,c,u){const z=nrm(sub(e,c)),x=nrm(cross(u,z)),y=cross(z,x);
    return[x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,
      -dot(x,e),-dot(y,e),-dot(z,e),1];}};

const cv=document.getElementById('cv');
const gl=cv.getContext('webgl2',{antialias:true,alpha:true,premultipliedAlpha:false});
const VS=`#version 300 es
in vec3 p; uniform mat4 uMVP; uniform vec3 uOfs; uniform float uS; out vec3 vP;
void main(){vec3 q=p*uS+uOfs; vP=q; gl_Position=uMVP*vec4(q,1.0);}`;
const FS=`#version 300 es
precision highp float; in vec3 vP; out vec4 o; uniform vec3 uC; uniform float uFlat;
void main(){
  vec3 n=normalize(cross(dFdx(vP),dFdy(vP)));
  float d=max(dot(n,normalize(vec3(.45,.55,.75))),0.0);
  vec3 c=mix(uC*0.30,uC,d*0.75+0.25);
  o=vec4(pow(mix(c,uC,uFlat),vec3(0.4545)),1.0);}`;
function sh(t,s){const o=gl.createShader(t);gl.shaderSource(o,s);gl.compileShader(o);
  if(!gl.getShaderParameter(o,gl.COMPILE_STATUS))console.error(gl.getShaderInfoLog(o));return o;}
const prog=gl.createProgram();
gl.attachShader(prog,sh(gl.VERTEX_SHADER,VS));gl.attachShader(prog,sh(gl.FRAGMENT_SHADER,FS));
gl.bindAttribLocation(prog,0,'p');gl.linkProgram(prog);gl.useProgram(prog);
const U=n=>gl.getUniformLocation(prog,n);
gl.enable(gl.DEPTH_TEST);

function buf(pos,idx,i32,short){
  const vao=gl.createVertexArray();gl.bindVertexArray(vao);
  const vb=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,vb);
  gl.bufferData(gl.ARRAY_BUFFER,pos,gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0);
  if(short)gl.vertexAttribPointer(0,3,gl.SHORT,true,0,0);
  else gl.vertexAttribPointer(0,3,gl.FLOAT,false,0,0);
  const ib=gl.createBuffer();gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,ib);
  gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,idx,gl.STATIC_DRAW);
  return{vao,ib,n:idx.length,type:i32?gl.UNSIGNED_INT:gl.UNSIGNED_SHORT};}

const parts=PIECES.map(p=>({...p,gpu:buf(b64(p.pos),b64(p.idx),p.i32,true)}));
// the path, as a line strip in world mm
const pathBuf=(()=>{const vao=gl.createVertexArray();gl.bindVertexArray(vao);
  const vb=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,vb);
  gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(PATH.flat()),gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0);gl.vertexAttribPointer(0,3,gl.FLOAT,false,0,0);
  return{vao,n:PATH.length};})();
// a unit sphere for the marble
const ball=(()=>{const S=16,P=[],I=[];
  for(let i=0;i<=S;i++){const th=i*Math.PI/S;for(let j=0;j<=S*2;j++){const ph=j*Math.PI/S;
    P.push(Math.sin(th)*Math.cos(ph),Math.sin(th)*Math.sin(ph),Math.cos(th));}}
  const W=S*2+1;
  for(let i=0;i<S;i++)for(let j=0;j<S*2;j++){const a=i*W+j,b=a+W;I.push(a,b,a+1,a+1,b,b+1);}
  return buf(new Float32Array(P),new Uint16Array(I),0,false);})();

const centre=CENTRE;
let az=-0.9,el=0.5,dist=DIST0,drag=null,playing=true,frameI=0,last=0;
const hex=h=>{const n=parseInt(h.slice(1),16),f=v=>Math.pow(v/255,2.2);
  return[f((n>>16)&255),f((n>>8)&255),f(n&255)];};

function draw(now){
  const idx=Math.min(PATH.length-1,frameI|0);
  const r=cv.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,2);
  const w=Math.round(r.width*dpr),h=Math.round(r.height*dpr);
  if(cv.width!==w||cv.height!==h){cv.width=w;cv.height=h;}
  gl.viewport(0,0,w,h);gl.clearColor(0,0,0,0);
  gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
  const ex=dist*Math.cos(el)*Math.sin(az),ey=dist*Math.cos(el)*Math.cos(az),ez=dist*Math.sin(el);
  const V=M4.look([centre[0]+ex,centre[1]+ey,centre[2]+ez],centre,[0,0,1]);
  const P=M4.persp(0.7,w/Math.max(h,1),1,4000);
  gl.uniformMatrix4fv(U('uMVP'),false,new Float32Array(M4.mul(P,V)));
  gl.uniform1f(U('uFlat'),0.0);
  parts.forEach((p,i)=>{
    gl.uniform3fv(U('uC'),hex(COLOURS[i%%COLOURS.length]));
    gl.uniform1f(U('uS'),p.scale);gl.uniform3fv(U('uOfs'),p.at);
    gl.bindVertexArray(p.gpu.vao);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,p.gpu.ib);
    gl.drawElements(gl.TRIANGLES,p.gpu.n,p.gpu.type,0);});
  // path
  gl.uniform1f(U('uFlat'),1.0);gl.uniform3fv(U('uC'),hex('#F2A03B'));
  gl.uniform1f(U('uS'),1.0);gl.uniform3fv(U('uOfs'),[0,0,0]);
  gl.bindVertexArray(pathBuf.vao);gl.drawArrays(gl.LINE_STRIP,0,pathBuf.n);
  // marble
  gl.uniform1f(U('uFlat'),0.0);gl.uniform3fv(U('uC'),hex('#D0341F'));
  gl.uniform1f(U('uS'),%(marble)f);gl.uniform3fv(U('uOfs'),PATH[idx]);
  gl.bindVertexArray(ball.vao);gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,ball.ib);
  gl.drawElements(gl.TRIANGLES,ball.n,ball.type,0);
  // advance by the wall clock, not by the frame: a sample is DT of simulated time, and one
  // sample per frame would run whatever speed the display happens to refresh at.
  if(playing){
    const d=last?Math.min((now-last)/1000,0.1):0; last=now;
    frameI+=d*SPEED/DT;
    if(frameI>PATH.length-1+HOLD*SPEED/DT)frameI=0;   // hold on the last frame, then loop
    scrub.value=idx;clock.textContent=(idx*DT).toFixed(2)+' s';
  }else last=0;
  requestAnimationFrame(draw);}

const scrub=document.getElementById('scrub'),clock=document.getElementById('clock');
document.getElementById('play').onclick=e=>{playing=!playing;
  e.target.textContent=playing?'Pause':'Play';};
scrub.oninput=e=>{playing=false;document.getElementById('play').textContent='Play';
  frameI=+e.target.value;clock.textContent=(frameI*DT).toFixed(2)+' s';};
document.getElementById('reset').onclick=()=>{az=-0.9;el=0.5;dist=DIST0;};
cv.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY};
  cv.setPointerCapture(e.pointerId);});
cv.addEventListener('pointermove',e=>{if(!drag)return;
  az-=(e.clientX-drag.x)*0.008;el=Math.max(-1.4,Math.min(1.4,el+(e.clientY-drag.y)*0.008));
  drag={x:e.clientX,y:e.clientY};});
addEventListener('pointerup',()=>drag=null);
cv.addEventListener('wheel',e=>{e.preventDefault();
  dist=Math.max(60,Math.min(900,dist*(1+Math.sign(e.deltaY)*0.09)));},{passive:false});
draw();
</script>
"""


def write(asm, result, out, title="assembly", sub=""):
    pieces = []
    for pc in asm.pieces:
        m = pc.mesh.copy()
        m.apply_translation(-pc.at)          # pack in the piece's own frame; offset in the shader
        d = _pack(m)
        d["at"] = [round(float(v), 2) for v in pc.at]
        pieces.append(d)

    # frame the assembly, not the path: a run that ends up in one corner would otherwise
    # point the camera at that corner and leave the piece it came out of off screen
    lo, hi = asm.solid.bounds
    centre = [round(float(v), 2) for v in (lo + hi) / 2]
    dist = round(float(np.linalg.norm(hi - lo)) * 1.9, 1)

    html = PAGE % dict(
        title=title, sub=sub, pieces=json.dumps(pieces, separators=(",", ":")),
        path=json.dumps(result["path"], separators=(",", ":")), dt=result["dt"],
        colours=json.dumps(COLOURS), nlast=max(len(result["path"]) - 1, 1),
        centre=json.dumps(centre), dist=dist,
        route=" &rarr; ".join(result["route"]) or "no port crossed",
        ending=result["ending"], seconds=result["t"], marble=MARBLE_R)
    pathlib.Path(out).write_text(html, encoding="utf8")
    return out, sum(p["tris"] for p in pieces), len(result["path"])


def main():
    asm = Assembly().add("spiral_ramp", (0, 0, 0)).add("teal", (0, 0, MINI_H))
    res = runner.drop(asm, feed=0.5, path_every=8)
    out, tris, n = write(
        asm, res, "/tmp/marble-run-view.html", title="the tower twister",
        sub="A block seated on the twister's tray: out of its 60&deg; side exit, round the "
            "270&deg; loop, and back in through the low bore on the next face.")
    print("%s  %d triangles, %d path samples, %.0f KB"
          % (out, tris, n, pathlib.Path(out).stat().st_size / 1024))
    print("route:", " -> ".join(res["route"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
