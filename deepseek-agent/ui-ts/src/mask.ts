/**
 * Anonymous Mask 3D — Pure TypeScript + Three.js
 * No external images. All geometry constructed from code.
 * Run: open index.html in browser (uses ESM import from CDN)
 */

import * as THREE from "three";

// ─── Types ────────────────────────────────────────────────────────────────────

type Vec3 = [number, number, number];

interface TubeConfig {
  points:   Vec3[];
  radius?:  number;
  mat?:     THREE.Material;
  segments?: number;
}

interface EllipseConfig {
  cx: number; cy: number; cz: number;
  rx: number; ry: number;
  mat?: THREE.Material;
}

interface NeonMaterials {
  outerBorder: THREE.MeshStandardMaterial;
  innerLine:   THREE.MeshStandardMaterial;
  accentGlow:  THREE.MeshStandardMaterial;
  faceBody:    THREE.MeshStandardMaterial;
}

// ─── Material Factory ─────────────────────────────────────────────────────────

function createMaterials(): NeonMaterials {
  return {
    outerBorder: new THREE.MeshStandardMaterial({
      color: 0xffe050, emissive: 0xffe050,
      emissiveIntensity: 2.8, roughness: 0.1, metalness: 0.4,
    }),
    innerLine: new THREE.MeshStandardMaterial({
      color: 0xffffff, emissive: 0xffffff,
      emissiveIntensity: 3.2, roughness: 0.1, metalness: 0.3,
    }),
    accentGlow: new THREE.MeshStandardMaterial({
      color: 0xffcc00, emissive: 0xffcc00,
      emissiveIntensity: 2.0, roughness: 0.2, metalness: 0.5,
    }),
    faceBody: new THREE.MeshStandardMaterial({
      color: 0x080808, roughness: 0.85, metalness: 0.15,
      side: THREE.FrontSide,
    }),
  };
}

// ─── Geometry Helpers ─────────────────────────────────────────────────────────

function makeTube({ points, radius = 0.025, mat, segments = 48 }: TubeConfig): THREE.Mesh {
  const curve = new THREE.CatmullRomCurve3(
    points.map(([x, y, z]) => new THREE.Vector3(x, y, z))
  );
  const geo  = new THREE.TubeGeometry(curve, segments, radius, 8, false);
  return new THREE.Mesh(geo, mat);
}

function makeEllipseRing({ cx, cy, cz, rx, ry, mat }: EllipseConfig): THREE.Mesh {
  const pts: Vec3[] = Array.from({ length: 65 }, (_, i) => {
    const a = (i / 64) * Math.PI * 2;
    return [cx + Math.cos(a) * rx, cy + Math.sin(a) * ry, cz];
  });
  return makeTube({ points: pts, radius: 0.022, mat, segments: 64 });
}

function makeClosedLoop(pts: Vec3[], radius: number, mat: THREE.Material): THREE.Mesh {
  return makeTube({ points: [...pts, pts[0]], radius, mat, segments: pts.length * 10 });
}

// ─── Face Base ────────────────────────────────────────────────────────────────

function buildFaceBase(group: THREE.Group, mats: NeonMaterials): void {
  // Extruded rounded rectangle for the face volume
  const shape = new THREE.Shape();
  const w = 1.05, h = 1.30, r = 0.28;
  shape.moveTo(-w + r, -h);
  shape.lineTo( w - r, -h);
  shape.quadraticCurveTo( w, -h,  w, -h + r);
  shape.lineTo( w,  h - r);
  shape.quadraticCurveTo( w,  h,  w - r,  h);
  shape.lineTo(-w + r,  h);
  shape.quadraticCurveTo(-w,  h, -w,  h - r);
  shape.lineTo(-w, -h + r);
  shape.quadraticCurveTo(-w, -h, -w + r, -h);

  const extSettings: THREE.ExtrudeGeometryOptions = {
    depth: 0.22,
    bevelEnabled:    true,
    bevelThickness:  0.07,
    bevelSize:       0.07,
    bevelSegments:   6,
  };

  const body = new THREE.Mesh(
    new THREE.ExtrudeGeometry(shape, extSettings),
    mats.faceBody
  );
  body.position.set(0, 0.05, -0.20);
  group.add(body);

  // Neon outer border — approximate rounded-rect with ellipse
  const borderPts: Vec3[] = Array.from({ length: 257 }, (_, i) => {
    const a = (i / 256) * Math.PI * 2;
    return [Math.cos(a) * (w - 0.02), Math.sin(a) * (h - 0.05) + 0.05, 0.12];
  });
  group.add(makeTube({ points: borderPts, radius: 0.034, mat: mats.outerBorder, segments: 256 }));
}

// ─── Eyebrows ─────────────────────────────────────────────────────────────────

function buildEyebrows(group: THREE.Group, mats: NeonMaterials): void {
  const browL: Vec3[] = [[-0.66, 0.61, 0.14], [-0.42, 0.73, 0.14], [-0.18, 0.64, 0.14]];
  const browR: Vec3[] = [[ 0.18, 0.64, 0.14], [ 0.42, 0.73, 0.14], [ 0.66, 0.61, 0.14]];
  group.add(makeTube({ points: browL, radius: 0.029, mat: mats.outerBorder }));
  group.add(makeTube({ points: browR, radius: 0.029, mat: mats.outerBorder }));
}

// ─── Eyes ─────────────────────────────────────────────────────────────────────

function buildEyes(group: THREE.Group, mats: NeonMaterials): void {
  const eyes: Array<{ x: number }> = [{ x: -0.40 }, { x: 0.40 }];

  for (const { x } of eyes) {
    const sign = x < 0 ? -1 : 1;

    // Outer socket
    group.add(makeEllipseRing({ cx: x, cy: 0.38, cz: 0.14, rx: 0.29, ry: 0.19, mat: mats.innerLine }));
    // Inner socket
    group.add(makeEllipseRing({ cx: x, cy: 0.38, cz: 0.17, rx: 0.16, ry: 0.11, mat: mats.innerLine }));

    // Corner bracket — inner
    const bi = x + sign * 0.10;
    group.add(makeTube({
      points: [[bi - sign * 0.06, 0.46, 0.14], [bi, 0.46, 0.14], [bi, 0.40, 0.14]],
      radius: 0.018, mat: mats.innerLine,
    }));
    // Corner bracket — outer
    const bo = x - sign * 0.28;
    group.add(makeTube({
      points: [[bo - sign * 0.06, 0.46, 0.14], [bo, 0.46, 0.14], [bo, 0.40, 0.14]],
      radius: 0.018, mat: mats.innerLine,
    }));
  }
}

// ─── Nose ─────────────────────────────────────────────────────────────────────

function buildNose(group: THREE.Group, mats: NeonMaterials): void {
  // Bridge
  group.add(makeTube({
    points: [[0, 0.28, 0.14], [0, 0.04, 0.16]],
    radius: 0.020, mat: mats.innerLine,
  }));

  // Wings
  const wingSides: Vec3[][] = [
    [[-0.17, 0.06, 0.14], [-0.10, 0.02, 0.16], [-0.05, 0.04, 0.15], [0, 0.04, 0.16]],
    [[ 0.17, 0.06, 0.14], [ 0.10, 0.02, 0.16], [ 0.05, 0.04, 0.15], [0, 0.04, 0.16]],
  ];
  for (const pts of wingSides) {
    group.add(makeTube({ points: pts, radius: 0.018, mat: mats.innerLine }));
  }

  // Nostril circles
  group.add(makeEllipseRing({ cx: -0.10, cy: 0.04, cz: 0.17, rx: 0.056, ry: 0.043, mat: mats.innerLine }));
  group.add(makeEllipseRing({ cx:  0.10, cy: 0.04, cz: 0.17, rx: 0.056, ry: 0.043, mat: mats.innerLine }));
}

// ─── Cheeks & Moustache ───────────────────────────────────────────────────────

function buildCheeksAndMoustache(group: THREE.Group, mats: NeonMaterials): void {
  // Cheek curves
  const cheekL: Vec3[] = [[-0.82, 0.10, 0.10], [-0.70, 0.08, 0.13], [-0.42, 0.00, 0.15], [-0.22, -0.04, 0.15]];
  const cheekR: Vec3[] = [[ 0.82, 0.10, 0.10], [ 0.70, 0.08, 0.13], [ 0.42, 0.00, 0.15], [ 0.22, -0.04, 0.15]];
  group.add(makeTube({ points: cheekL, radius: 0.025, mat: mats.outerBorder }));
  group.add(makeTube({ points: cheekR, radius: 0.025, mat: mats.outerBorder }));

  // Moustache curls
  const moustL: Vec3[] = [
    [-0.22, -0.04, 0.15], [-0.38, -0.10, 0.14], [-0.53, -0.08, 0.13],
    [-0.60, -0.15, 0.12], [-0.53, -0.23, 0.13], [-0.38, -0.21, 0.14],
    [-0.25, -0.13, 0.15], [-0.12, -0.08, 0.15],
  ];
  const moustR: Vec3[] = [
    [ 0.22, -0.04, 0.15], [ 0.38, -0.10, 0.14], [ 0.53, -0.08, 0.13],
    [ 0.60, -0.15, 0.12], [ 0.53, -0.23, 0.13], [ 0.38, -0.21, 0.14],
    [ 0.25, -0.13, 0.15], [ 0.12, -0.08, 0.15],
  ];
  group.add(makeTube({ points: moustL, radius: 0.022, mat: mats.innerLine }));
  group.add(makeTube({ points: moustR, radius: 0.022, mat: mats.innerLine }));
}

// ─── Mouth ────────────────────────────────────────────────────────────────────

function buildMouth(group: THREE.Group, mats: NeonMaterials): void {
  // Upper lip
  group.add(makeTube({
    points: [[-0.30, -0.22, 0.15], [0, -0.18, 0.16], [0.30, -0.22, 0.15]],
    radius: 0.020, mat: mats.innerLine,
  }));

  // Smile arc
  group.add(makeTube({
    points: [
      [-0.45, -0.32, 0.13], [-0.30, -0.46, 0.15],
      [0, -0.49, 0.16],
      [ 0.30, -0.46, 0.15], [ 0.45, -0.32, 0.13],
    ],
    radius: 0.022, mat: mats.innerLine,
  }));

  // Dimple connectors
  group.add(makeTube({ points: [[-0.45, -0.32, 0.13], [-0.38, -0.22, 0.14]], radius: 0.020, mat: mats.innerLine }));
  group.add(makeTube({ points: [[ 0.45, -0.32, 0.13], [ 0.38, -0.22, 0.14]], radius: 0.020, mat: mats.innerLine }));

  // Mouth triangle (chin guard)
  group.add(makeClosedLoop(
    [[-0.13, -0.24, 0.15], [0, -0.33, 0.16], [0.13, -0.24, 0.15]],
    0.017, mats.innerLine
  ));

  // Chin vertical
  group.add(makeTube({ points: [[0, -0.49, 0.15], [0, -0.72, 0.12]], radius: 0.018, mat: mats.innerLine }));

  // Chin fork
  group.add(makeTube({
    points: [[-0.19, -0.82, 0.10], [0, -0.72, 0.12], [0.19, -0.82, 0.10]],
    radius: 0.018, mat: mats.innerLine,
  }));
}

// ─── Code Symbols  { #} ───────────────────────────────────────────────────────

function buildCodeSymbols(group: THREE.Group, mats: NeonMaterials): void {
  // Left brace  {
  group.add(makeTube({
    points: [
      [-0.82,  0.06, 0.10], [-0.87,  0.02, 0.10],
      [-0.91, -0.02, 0.10], [-0.87, -0.06, 0.10],
      [-0.82, -0.11, 0.10],
    ],
    radius: 0.016, mat: mats.accentGlow,
  }));

  // Hash symbol  #  on right cheek
  const hx = 0.70, hy = -0.05, hz = 0.14, s = 0.082;
  // Horizontal bars
  group.add(makeTube({ points: [[hx - s, hy + 0.032, hz], [hx + s, hy + 0.032, hz]], radius: 0.014, mat: mats.innerLine }));
  group.add(makeTube({ points: [[hx - s, hy - 0.032, hz], [hx + s, hy - 0.032, hz]], radius: 0.014, mat: mats.innerLine }));
  // Vertical bars
  group.add(makeTube({ points: [[hx - 0.030, hy + s, hz], [hx - 0.030, hy - s, hz]], radius: 0.014, mat: mats.innerLine }));
  group.add(makeTube({ points: [[hx + 0.030, hy + s, hz], [hx + 0.030, hy - s, hz]], radius: 0.014, mat: mats.innerLine }));

  // Right brace  }
  group.add(makeTube({
    points: [
      [ 0.82,  0.06, 0.10], [ 0.87,  0.02, 0.10],
      [ 0.91, -0.02, 0.10], [ 0.87, -0.06, 0.10],
      [ 0.82, -0.11, 0.10],
    ],
    radius: 0.016, mat: mats.accentGlow,
  }));
}

// ─── Halo Rings ───────────────────────────────────────────────────────────────

function buildHalo(group: THREE.Group): void {
  const halos: Array<{ inner: number; outer: number; opacity: number }> = [
    { inner: 1.30, outer: 1.46, opacity: 0.18 },
    { inner: 1.52, outer: 1.72, opacity: 0.09 },
    { inner: 1.78, outer: 1.92, opacity: 0.04 },
  ];
  for (const { inner, outer, opacity } of halos) {
    const geo = new THREE.RingGeometry(inner, outer, 128);
    const mat = new THREE.MeshBasicMaterial({
      color: 0xffe050, transparent: true, opacity, side: THREE.DoubleSide,
    });
    const ring = new THREE.Mesh(geo, mat);
    ring.position.z = -0.06;
    group.add(ring);
  }
}

// ─── Particle Field ───────────────────────────────────────────────────────────

function buildParticles(scene: THREE.Scene): void {
  const COUNT = 700;
  const pos   = new Float32Array(COUNT * 3);
  for (let i = 0; i < COUNT; i++) {
    pos[i * 3]     = (Math.random() - 0.5) * 22;
    pos[i * 3 + 1] = (Math.random() - 0.5) * 22;
    pos[i * 3 + 2] = (Math.random() - 0.5) * 10 - 5;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const mat = new THREE.PointsMaterial({ color: 0xffe050, size: 0.03, transparent: true, opacity: 0.45 });
  scene.add(new THREE.Points(geo, mat));
}

// ─── Lighting ─────────────────────────────────────────────────────────────────

function setupLights(scene: THREE.Scene): THREE.PointLight {
  scene.add(new THREE.AmbientLight(0x111111, 1.2));

  const front = new THREE.PointLight(0xffffff, 1.8, 12);
  front.position.set(0, 1, 4);
  scene.add(front);

  const rim = new THREE.PointLight(0xffe060, 5, 14);
  rim.position.set(0, 0, -3);
  scene.add(rim);

  const left  = new THREE.PointLight(0xffe060, 2.5, 10);
  left.position.set(-3, 0.5, 2);
  scene.add(left);

  const right = new THREE.PointLight(0xffe060, 2.5, 10);
  right.position.set( 3, 0.5, 2);
  scene.add(right);

  return rim; // returned for animation
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export function init(canvas: HTMLCanvasElement): () => void {
  // Renderer
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.shadowMap.enabled = true;

  // Scene & Camera
  const scene  = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 100);
  camera.position.set(0, 0, 5);

  // Materials
  const mats = createMaterials();

  // Build mask
  const maskGroup = new THREE.Group();
  buildFaceBase(maskGroup, mats);
  buildEyebrows(maskGroup, mats);
  buildEyes(maskGroup, mats);
  buildNose(maskGroup, mats);
  buildCheeksAndMoustache(maskGroup, mats);
  buildMouth(maskGroup, mats);
  buildCodeSymbols(maskGroup, mats);
  buildHalo(maskGroup);
  scene.add(maskGroup);

  // World
  buildParticles(scene);
  const rimLight = setupLights(scene);

  // Resize handler
  const onResize = (): void => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  };
  window.addEventListener("resize", onResize);

  // Animation loop
  let time = 0;
  let rafId = 0;

  const tick = (): void => {
    rafId = requestAnimationFrame(tick);
    time += 0.008;

    // Spin
    maskGroup.rotation.y = time * 1.2;

    // Bob
    maskGroup.position.y = Math.sin(time * 0.8) * 0.06;

    // Neon pulse
    const pulse = 2.0 + Math.sin(time * 3) * 0.8;
    mats.outerBorder.emissiveIntensity = pulse;
    mats.innerLine.emissiveIntensity   = pulse + 0.6;
    mats.accentGlow.emissiveIntensity  = pulse - 0.3;

    // Rim light orbit
    rimLight.position.x = Math.sin(time * 0.7) * 3;
    rimLight.position.y = Math.cos(time * 0.5) * 1.5;

    renderer.render(scene, camera);
  };
  tick();

  // Return cleanup function
  return (): void => {
    cancelAnimationFrame(rafId);
    window.removeEventListener("resize", onResize);
    renderer.dispose();
  };
}
