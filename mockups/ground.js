// The ground: three hard-edged planes on ink, and the milk-glass sheet drawn over them in one pass.
(() => {
  const FRAG = `
precision highp float;
uniform vec2 R; uniform float D;
uniform vec2 P[12]; uniform vec3 C[4];
uniform vec4 S; uniform float SA; uniform vec3 T;
float side(vec2 p, vec2 a, vec2 b) { vec2 e = b - a; return dot(p - a, normalize(vec2(e.y, -e.x))); }
float poly(vec2 p, vec2 a, vec2 b, vec2 c, vec2 d) { return max(max(side(p, a, b), side(p, b, c)), max(side(p, c, d), side(p, d, a))); }
float cover(float d, float w) { return 1.0 - smoothstep(-w, w, d); }
vec3 ground(vec2 p, float w) {
  vec3 col = C[0];
  col = mix(col, C[1], cover(poly(p, P[0], P[1], P[2], P[3]), w));
  col = mix(col, C[2], cover(poly(p, P[4], P[5], P[6], P[7]), w));
  return mix(col, C[3], cover(poly(p, P[8], P[9], P[10], P[11]), w));
}
float box(vec2 p) { vec2 h = S.zw * 0.5; vec2 q = abs(p - S.xy - h) - h + 28.0 * D; return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - 28.0 * D; }
float grain(vec2 p) { return fract(sin(dot(floor(p / D), vec2(12.9898, 78.233))) * 43758.5453); }
void main() {
  vec2 p = vec2(gl_FragCoord.x, R.y - gl_FragCoord.y);
  vec3 bare = ground(p, 0.8 * D);
  float sd = box(p);
  float drop = (1.0 - smoothstep(-60.0 * D, 120.0 * D, box(p - vec2(0.0, 44.0 * D)))) * 0.62 * SA;
  vec3 outside = bare * (1.0 - drop * step(0.0, sd));
  if (SA <= 0.001 || sd > 1.5 * D) { gl_FragColor = vec4(outside, 1.0); return; }
  float band = 24.0 * D;
  float u = clamp(1.0 + sd / band, 0.0, 1.0);
  vec2 n = normalize(vec2(box(p + vec2(D, 0.0)) - box(p - vec2(D, 0.0)), box(p + vec2(0.0, D)) - box(p - vec2(0.0, D))) + 1e-5);
  vec2 q = p - n * band * 1.6 * u * u;
  vec3 fog = ground(q, mix(64.0, 7.0, u * u) * D);
  float luma = dot(fog, vec3(0.299, 0.587, 0.114));
  fog = mix(vec3(luma), fog, 1.08);
  fog = mix(fog, C[0], 0.30);
  fog = mix(fog, T, 0.10) + 0.045;
  fog += (grain(p) - 0.5) * 0.06;
  float top = exp(-max(p.y - S.y, 0.0) / (7.0 * D)) * (1.0 - smoothstep(0.0, 0.9, abs((p.x - S.x) / S.z - 0.32)));
  fog += vec3(0.95, 0.94, 0.91) * 0.16 * top * step(sd, 0.0);
  vec3 edgeHue = mix(bare, vec3(0.95, 0.94, 0.91), 0.42) + 0.04;
  float edge = 1.0 - smoothstep(0.0, 1.1 * D, abs(sd + 0.6 * D));
  vec3 glass = mix(fog, edgeHue, edge * 0.9);
  float inside = 1.0 - smoothstep(-0.6 * D, 0.6 * D, sd);
  gl_FragColor = vec4(mix(outside, glass, max(inside, edge) * SA), 1.0);
}`;
  const VERT = "attribute vec2 a; void main() { gl_Position = vec4(a, 0.0, 1.0); }";

  // Planes in viewport fractions, clockwise on screen; wide enough to slide without showing an edge.
  const PLANES = [
    [[-0.3, 0.74], [0.28, 0.63], [0.4, 1.2], [-0.3, 1.2]],
    [[0.8, 0.13], [1.3, 0.02], [1.3, 0.52], [0.87, 0.38]],
    [[0.93, 0.6], [1.3, 0.5], [1.3, 1.2], [0.975, 1.2]],
  ];
  const SLIDE = [1, 1, 0.35];
  const DRIFT = [[0.9, 0.0, 0.031, 0.024], [1.3, 2.1, 0.026, 0.035], [0.7, 4.2, 0.037, 0.029]];

  const canvas = document.querySelector(".ground");
  const gl = canvas && canvas.getContext("webgl", { antialias: false, alpha: false, preserveDrawingBuffer: false });
  const stats = { deltas: [], renderer: "none", software: false };
  window.Ground = { ok: false, stats, draw() {} };
  if (!gl) return;

  const compile = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); return s; };
  const prog = gl.createProgram();
  gl.attachShader(prog, compile(gl.VERTEX_SHADER, VERT));
  gl.attachShader(prog, compile(gl.FRAGMENT_SHADER, FRAG));
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) { console.error(gl.getShaderInfoLog(compile(gl.FRAGMENT_SHADER, FRAG))); return; }
  gl.useProgram(prog);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
  const U = (n) => gl.getUniformLocation(prog, n);
  const loc = { R: U("R"), D: U("D"), P: U("P"), C: U("C"), S: U("S"), SA: U("SA"), T: U("T") };

  const info = gl.getExtension("WEBGL_debug_renderer_info");
  stats.renderer = info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
  stats.software = /swiftshader|llvmpipe|software|basic render/i.test(stats.renderer);

  // oklch tokens to sRGB, so the shader paints the same colours the CSS names.
  const oklch = (str) => {
    const [L, Cc, h] = str.match(/[\d.]+/g).map(Number);
    const a = Cc * Math.cos((h * Math.PI) / 180), b = Cc * Math.sin((h * Math.PI) / 180), l0 = L / 100;
    const l = (l0 + 0.3963377774 * a + 0.2158037573 * b) ** 3, m = (l0 - 0.1055613458 * a - 0.0638541728 * b) ** 3, s = (l0 - 0.0894841775 * a - 1.291485548 * b) ** 3;
    const lin = [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s, -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s];
    return lin.map((x) => { x = Math.min(1, Math.max(0, x)); return x <= 0.0031308 ? 12.92 * x : 1.055 * x ** (1 / 2.4) - 0.055; });
  };
  const token = (name) => oklch(getComputedStyle(document.documentElement).getPropertyValue(name));
  const COL = ["--ink", "--teal", "--oxblood", "--sand"].map(token);
  const TINT = { guard: token("--red"), reader: token("--teal"), prover: token("--sand"), keeper: token("--ivory") };
  gl.uniform3fv(loc.C, COL.flat());

  const fit = () => {
    // Software GL draws the ground at half resolution; the planes are soft under glass anyway.
    const dpr = stats.software ? 0.5 : Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.round(innerWidth * dpr); canvas.height = Math.round(innerHeight * dpr);
    gl.viewport(0, 0, canvas.width, canvas.height); return dpr;
  };
  let dpr = fit();
  addEventListener("resize", () => { dpr = fit(); });

  const planePoints = (offsets) => PLANES.flatMap((pl, i) => pl.flatMap(([x, y]) => [(x * innerWidth + offsets[i][0]) * dpr, (y * innerHeight + offsets[i][1]) * dpr]));
  const drift = (i, s, amp) => { const [ax, ph, wx, wy] = DRIFT[i]; return [amp * ax * Math.sin(s * wx + ph), amp * Math.cos(s * wy + ph * 0.7)]; };

  // frame: { driftS, amp, pull[3][2], shift, pointer[2], sheet: DOMRect|null, alpha, pillar }
  window.Ground.draw = (f) => {
    const offsets = [0, 1, 2].map((i) => {
      const d = drift(i, f.driftS, f.amp), depth = (i + 1) * 2;
      return [d[0] + f.pull[i][0] + f.shift * SLIDE[i] + f.pointer[0] * depth, d[1] + f.pull[i][1] + f.pointer[1] * depth];
    });
    gl.uniform2f(loc.R, canvas.width, canvas.height); gl.uniform1f(loc.D, dpr * (f.k || 1));
    gl.uniform2fv(loc.P, planePoints(offsets));
    const r = f.sheet;
    gl.uniform4f(loc.S, r ? r.left * dpr : 0, r ? r.top * dpr : 0, r ? r.width * dpr : 1, r ? r.height * dpr : 1);
    gl.uniform1f(loc.SA, r ? f.alpha : 0);
    gl.uniform3fv(loc.T, TINT[f.pillar] || TINT.keeper);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  };
  window.Ground.ok = true;
  window.Ground.dpr = () => dpr;
})();
