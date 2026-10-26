'use client';

import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { Layers, RotateCcw } from 'lucide-react';

export interface RoomState {
  id: string;
  name: string;
  floor: number;
  type: string;
  state: string; // NORMAL, ATTENTION, ANOMALY, INCIDENT, OFFLINE
}

export interface RoomTelemetrySnapshot {
  temperature: number;
  humidity: number;
  gas: number;
  smoke: number;
  occupancy: number;
  vibration: number;
}

interface Building3DProps {
  rooms: RoomState[];
  selectedRoomId: string | null;
  onSelectRoom: (roomId: string) => void;
  telemetryByRoom?: Record<string, RoomTelemetrySnapshot>;
  theme?: 'daylight' | 'midnight';
}

interface RoomGeometryConfig {
  id: string;
  name: string;
  x: number;
  y: number;
  z: number;
  w: number;
  h: number;
  d: number;
  floor: number;
  kind: 'portal' | 'atrium' | 'classroom' | 'server' | 'lab' | 'storage';
}

export const FACILITY_ROOM_CONFIGS: RoomGeometryConfig[] = [
  { id: 'entrance', name: 'Main Entrance', x: 0, y: 1.4, z: 5.0, w: 7.4, h: 2.8, d: 4.4, floor: 1, kind: 'portal' },
  { id: 'main_hall', name: 'Main Hall', x: 0, y: 1.4, z: -1.8, w: 11.2, h: 2.8, d: 7.0, floor: 1, kind: 'atrium' },
  { id: 'classroom_01', name: 'Classroom 01', x: -9.2, y: 1.4, z: -1.8, w: 6.2, h: 2.8, d: 6.6, floor: 1, kind: 'classroom' },
  { id: 'classroom_02', name: 'Classroom 02', x: 9.2, y: 1.4, z: -1.8, w: 6.2, h: 2.8, d: 6.6, floor: 1, kind: 'classroom' },
  { id: 'server_room', name: 'Server Room', x: -8.4, y: 1.4, z: 5.0, w: 5.6, h: 2.8, d: 4.4, floor: 1, kind: 'server' },
  { id: 'emergency_exit', name: 'Emergency Exit', x: 8.4, y: 1.4, z: 5.0, w: 5.6, h: 2.8, d: 4.4, floor: 1, kind: 'portal' },
  { id: 'lab_01', name: 'Computer Lab 01', x: -8.2, y: 5.0, z: -1.8, w: 6.8, h: 2.8, d: 6.6, floor: 2, kind: 'lab' },
  { id: 'lab_02', name: 'Chemistry Lab 02', x: 8.2, y: 5.0, z: -1.8, w: 6.8, h: 2.8, d: 6.6, floor: 2, kind: 'lab' },
  { id: 'storage_room', name: 'Chemical Storage', x: 0, y: 5.0, z: -2.4, w: 6.6, h: 2.8, d: 5.2, floor: 2, kind: 'storage' },
];

export default function Building3D({
  rooms,
  selectedRoomId,
  onSelectRoom,
  telemetryByRoom = {},
  theme = 'daylight',
}: Building3DProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const pinRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  const [floorFilter, setFloorFilter] = useState<'all' | 1 | 2>('all');
  const [splitFloors, setSplitFloors] = useState<boolean>(false);
  const [hoveredRoomId, setHoveredRoomId] = useState<string | null>(null);

  const roomsRef = useRef<RoomState[]>(rooms);
  const selectedRoomIdRef = useRef<string | null>(selectedRoomId);
  const hoveredRoomIdRef = useRef<string | null>(hoveredRoomId);
  const floorFilterRef = useRef<'all' | 1 | 2>(floorFilter);
  const splitFloorsRef = useRef<boolean>(splitFloors);
  const themeRef = useRef<'daylight' | 'midnight'>(theme);
  const onSelectRoomRef = useRef(onSelectRoom);

  useEffect(() => { roomsRef.current = rooms; }, [rooms]);
  useEffect(() => { selectedRoomIdRef.current = selectedRoomId; }, [selectedRoomId]);
  useEffect(() => { hoveredRoomIdRef.current = hoveredRoomId; }, [hoveredRoomId]);
  useEffect(() => { floorFilterRef.current = floorFilter; }, [floorFilter]);
  useEffect(() => { splitFloorsRef.current = splitFloors; }, [splitFloors]);
  useEffect(() => { themeRef.current = theme; }, [theme]);
  useEffect(() => { onSelectRoomRef.current = onSelectRoom; }, [onSelectRoom]);

  const sphericalTargetRef = useRef({ theta: 0.65, phi: 1.04, radius: 32 });
  const sphericalCurrentRef = useRef({ theta: 0.65, phi: 1.04, radius: 32 });

  const handleResetCamera = () => {
    sphericalTargetRef.current = {
      theta: 0.65,
      phi: 1.04,
      radius: splitFloors ? 36 : 32,
    };
  };

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const width = mount.clientWidth || 800;
    const height = mount.clientHeight || 460;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 1000);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(width, height);
    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    mount.appendChild(renderer.domElement);

    // Clean Architectural Studio Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
    scene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0xffffff, 1.15);
    keyLight.position.set(24, 38, 24);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.width = 1024;
    keyLight.shadow.mapSize.height = 1024;
    keyLight.shadow.bias = -0.0005;
    scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0x94a3b8, 0.4);
    fillLight.position.set(-22, 16, -20);
    scene.add(fillLight);

    // Subtle Ground Grid
    const gridHelper = new THREE.GridHelper(54, 27, 0x94a3b8, 0xcbd5e1);
    gridHelper.position.y = -0.02;
    (gridHelper.material as THREE.Material).transparent = true;
    (gridHelper.material as THREE.Material).opacity = 0.35;
    scene.add(gridHelper);

    // Floor 2 Platform Slab
    const slabGroup = new THREE.Group();
    const slabGeo = new THREE.BoxGeometry(24.5, 0.14, 15.0);
    const slabMat = new THREE.MeshStandardMaterial({
      color: 0xcbd5e1,
      transparent: true,
      opacity: 0.35,
      roughness: 0.7,
    });
    const slabMesh = new THREE.Mesh(slabGeo, slabMat);
    slabMesh.position.set(0, 3.5, -0.5);
    slabGroup.add(slabMesh);
    scene.add(slabGroup);

    // Build clean interior furniture silhouettes
    const buildSimpleInterior = (cfg: RoomGeometryConfig) => {
      const group = new THREE.Group();
      const mat = new THREE.MeshStandardMaterial({
        color: 0x64748b,
        roughness: 0.5,
        metalness: 0.2,
        transparent: true,
        opacity: 0.45,
      });

      const baseFloorY = -cfg.h / 2 + 0.1;
      const addBlock = (bx: number, by: number, bz: number, bw: number, bh: number, bd: number) => {
        const m = new THREE.Mesh(new THREE.BoxGeometry(bw, bh, bd), mat);
        m.position.set(bx, by, bz);
        group.add(m);
      };

      if (cfg.kind === 'server') {
        [-1.4, -0.4, 0.6, 1.6].forEach((rx) => addBlock(rx, baseFloorY + 0.8, -0.3, 0.55, 1.6, 1.4));
      } else if (cfg.kind === 'lab') {
        addBlock(-1.2, baseFloorY + 0.4, -0.8, 2.0, 0.8, 1.1);
        addBlock(-1.2, baseFloorY + 0.4, 0.9, 2.0, 0.8, 1.1);
        addBlock(1.6, baseFloorY + 0.8, 0, 1.0, 1.6, 2.8);
      } else if (cfg.kind === 'classroom') {
        [-1.3, 1.3].forEach((dx) => {
          [-0.4, 1.0].forEach((dz) => addBlock(dx, baseFloorY + 0.35, dz, 1.5, 0.7, 0.7));
        });
      }
      return group;
    };

    const roomObjects: Record<
      string,
      {
        cfg: RoomGeometryConfig;
        group: THREE.Group;
        shellMesh: THREE.Mesh;
        floorPlate: THREE.Mesh;
        wireframe: THREE.LineSegments;
      }
    > = {};

    const interactiveMeshes: THREE.Object3D[] = [];

    FACILITY_ROOM_CONFIGS.forEach((cfg) => {
      const group = new THREE.Group();
      group.position.set(cfg.x, cfg.y, cfg.z);

      const shellGeo = new THREE.BoxGeometry(cfg.w - 0.35, cfg.h, cfg.d - 0.35);
      const shellMat = new THREE.MeshStandardMaterial({
        color: 0x10b981,
        transparent: true,
        opacity: 0.22,
        roughness: 0.25,
        metalness: 0.1,
        depthWrite: false,
      });
      const shellMesh = new THREE.Mesh(shellGeo, shellMat);
      shellMesh.userData = { roomId: cfg.id, name: cfg.name, floor: cfg.floor };
      group.add(shellMesh);
      interactiveMeshes.push(shellMesh);

      const plateGeo = new THREE.BoxGeometry(cfg.w - 0.4, 0.14, cfg.d - 0.4);
      const plateMat = new THREE.MeshStandardMaterial({
        color: 0xe2e8f0,
        roughness: 0.6,
        transparent: true,
        opacity: 0.9,
      });
      const floorPlate = new THREE.Mesh(plateGeo, plateMat);
      floorPlate.position.set(0, -cfg.h / 2 + 0.07, 0);
      group.add(floorPlate);

      const edges = new THREE.EdgesGeometry(shellGeo);
      const wireMat = new THREE.LineBasicMaterial({
        color: 0x10b981,
        transparent: true,
        opacity: 0.75,
      });
      const wireframe = new THREE.LineSegments(edges, wireMat);
      group.add(wireframe);

      group.add(buildSimpleInterior(cfg));

      scene.add(group);
      roomObjects[cfg.id] = { cfg, group, shellMesh, floorPlate, wireframe };
    });

    // Mouse Orbit & Click Selection
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    let isDragging = false;
    let downX = 0;
    let downY = 0;
    let prevX = 0;
    let prevY = 0;

    const onPointerDown = (e: MouseEvent) => {
      isDragging = true;
      downX = e.clientX;
      downY = e.clientY;
      prevX = e.clientX;
      prevY = e.clientY;
    };

    const onPointerMove = (e: MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      if (isDragging) {
        const dx = e.clientX - prevX;
        const dy = e.clientY - prevY;
        prevX = e.clientX;
        prevY = e.clientY;

        sphericalTargetRef.current.theta -= dx * 0.007;
        sphericalTargetRef.current.phi = Math.max(
          0.25,
          Math.min(Math.PI / 2 - 0.08, sphericalTargetRef.current.phi - dy * 0.006)
        );
        mount.style.cursor = 'grabbing';
        return;
      }

      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(mouse, camera);
      const hits = raycaster.intersectObjects(interactiveMeshes);
      if (hits.length > 0) {
        setHoveredRoomId(hits[0].object.userData.roomId);
        mount.style.cursor = 'pointer';
      } else {
        setHoveredRoomId(null);
        mount.style.cursor = 'grab';
      }
    };

    const onPointerUp = (e: MouseEvent) => {
      if (!isDragging) return;
      isDragging = false;
      const dist = Math.hypot(e.clientX - downX, e.clientY - downY);
      if (dist < 6) {
        const rect = renderer.domElement.getBoundingClientRect();
        mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
        raycaster.setFromCamera(mouse, camera);
        const hits = raycaster.intersectObjects(interactiveMeshes);
        if (hits.length > 0) {
          onSelectRoomRef.current(hits[0].object.userData.roomId);
        }
      }
      mount.style.cursor = 'grab';
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      sphericalTargetRef.current.radius = Math.max(
        18,
        Math.min(48, sphericalTargetRef.current.radius + e.deltaY * 0.02)
      );
    };

    mount.addEventListener('mousedown', onPointerDown);
    window.addEventListener('mousemove', onPointerMove);
    window.addEventListener('mouseup', onPointerUp);
    mount.addEventListener('wheel', onWheel, { passive: false });

    let animationFrameId: number;
    const clock = new THREE.Clock();
    const projVec = new THREE.Vector3();
    const lookTarget = new THREE.Vector3(0, 2.6, 0);

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      const time = clock.getElapsedTime();

      const isSplit = splitFloorsRef.current;
      const curFloorFilter = floorFilterRef.current;
      const curTheme = themeRef.current;
      const activeSelectedId = selectedRoomIdRef.current;
      const activeHoveredId = hoveredRoomIdRef.current;

      // Smoothly lift Floor 2 when Split View is active
      const targetOffset = isSplit ? 4.8 : 0;
      slabGroup.position.y += (targetOffset - slabGroup.position.y) * 0.1;

      // Smooth Camera Orbit
      sphericalCurrentRef.current.theta += (sphericalTargetRef.current.theta - sphericalCurrentRef.current.theta) * 0.08;
      sphericalCurrentRef.current.phi += (sphericalTargetRef.current.phi - sphericalCurrentRef.current.phi) * 0.08;
      sphericalCurrentRef.current.radius += (sphericalTargetRef.current.radius - sphericalCurrentRef.current.radius) * 0.08;

      const r = sphericalCurrentRef.current.radius;
      const phi = sphericalCurrentRef.current.phi;
      const theta = sphericalCurrentRef.current.theta;

      lookTarget.y += ((isSplit ? 4.0 : 2.5) - lookTarget.y) * 0.08;
      camera.position.x = r * Math.sin(phi) * Math.sin(theta);
      camera.position.y = lookTarget.y + r * Math.cos(phi);
      camera.position.z = r * Math.sin(phi) * Math.cos(theta);
      camera.lookAt(lookTarget);

      const cWidth = mount.clientWidth;
      const cHeight = mount.clientHeight;

      FACILITY_ROOM_CONFIGS.forEach((cfg) => {
        const obj = roomObjects[cfg.id];
        if (!obj) return;

        const targetY = cfg.y + (cfg.floor === 2 ? slabGroup.position.y : 0);
        obj.group.position.y += (targetY - obj.group.position.y) * 0.1;

        const roomData = roomsRef.current.find((rm) => rm.id === cfg.id);
        const state = roomData?.state || 'NORMAL';
        const isSelected = cfg.id === activeSelectedId;
        const isHovered = cfg.id === activeHoveredId;

        let fillHex = 0x10b981; // Emerald Normal
        let wireHex = curTheme === 'daylight' ? 0x059669 : 0x34d399;
        let opacity = curTheme === 'daylight' ? 0.20 : 0.26;

        if (state === 'INCIDENT') {
          const pulse = (Math.sin(time * 7) + 1) * 0.5;
          fillHex = 0xef4444;
          wireHex = 0xdc2626;
          opacity = 0.42 + pulse * 0.22;
        } else if (state === 'ANOMALY' || state === 'ATTENTION') {
          fillHex = 0xf59e0b;
          wireHex = 0xd97706;
          opacity = 0.36;
        } else if (state === 'OFFLINE') {
          fillHex = 0x94a3b8;
          wireHex = 0x64748b;
          opacity = 0.12;
        }

        if (isSelected) {
          wireHex = 0x2563eb; // Crisp Royal Blue for selected room
          if (state === 'NORMAL') {
            fillHex = 0x3b82f6;
          }
          opacity = Math.min(0.65, opacity + 0.18);
        } else if (isHovered) {
          opacity = Math.min(0.55, opacity + 0.1);
        }

        const dimmed = curFloorFilter !== 'all' && cfg.floor !== curFloorFilter;
        if (dimmed) opacity *= 0.12;

        (obj.shellMesh.material as THREE.MeshStandardMaterial).color.setHex(fillHex);
        (obj.shellMesh.material as THREE.MeshStandardMaterial).opacity = opacity;
        (obj.wireframe.material as THREE.LineBasicMaterial).color.setHex(wireHex);
        (obj.wireframe.material as THREE.LineBasicMaterial).opacity = dimmed ? 0.15 : isSelected ? 1.0 : 0.65;

        (obj.floorPlate.material as THREE.MeshStandardMaterial).color.setHex(
          curTheme === 'daylight' ? (isSelected ? 0xdbeafe : 0xe2e8f0) : isSelected ? 0x1e3a8a : 0x1e293b
        );
        (obj.floorPlate.material as THREE.MeshStandardMaterial).opacity = dimmed ? 0.15 : 0.9;

        // Position clean floating badge ONLY for Selected, Hovered, or Incident rooms
        const pinEl = pinRefs.current[cfg.id];
        if (pinEl) {
          const shouldShowPin = !dimmed && (isSelected || isHovered || state === 'INCIDENT');
          if (!shouldShowPin) {
            pinEl.style.opacity = '0';
            pinEl.style.pointerEvents = 'none';
          } else {
            projVec.set(cfg.x, obj.group.position.y + cfg.h / 2 + 0.5, cfg.z);
            projVec.project(camera);
            const sx = (projVec.x * 0.5 + 0.5) * cWidth;
            const sy = (-(projVec.y * 0.5) + 0.5) * cHeight;
            pinEl.style.opacity = '1';
            pinEl.style.pointerEvents = 'auto';
            pinEl.style.transform = `translate3d(${sx}px, ${sy}px, 0) translate(-50%, -100%)`;
          }
        }
      });

      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      if (!mount) return;
      const w = mount.clientWidth;
      const h = mount.clientHeight;
      if (w === 0 || h === 0) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animationFrameId);
      mount.removeEventListener('mousedown', onPointerDown);
      window.removeEventListener('mousemove', onPointerMove);
      window.removeEventListener('mouseup', onPointerUp);
      mount.removeEventListener('wheel', onWheel);
      window.removeEventListener('resize', handleResize);
      if (mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, []);

  const selectedRoomObj = rooms.find((r) => r.id === selectedRoomId);

  return (
    <div
      className={`relative w-full h-full min-h-[400px] rounded-2xl overflow-hidden select-none transition-colors ${
        theme === 'daylight'
          ? 'bg-gradient-to-b from-slate-100 to-slate-200/70 border border-slate-200/80'
          : 'bg-gradient-to-b from-[#131923] to-[#0d1219] border border-white/10'
      }`}
    >
      <div ref={mountRef} className="w-full h-full cursor-grab" />

      {/* Minimal Floating Badges — ONLY shown on Selected, Hovered, or Active Alert Rooms */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden z-10">
        {FACILITY_ROOM_CONFIGS.map((cfg) => {
          const roomState = rooms.find((r) => r.id === cfg.id)?.state || 'NORMAL';
          const telem = telemetryByRoom[cfg.id];
          const isSelected = selectedRoomId === cfg.id;
          const isIncident = roomState === 'INCIDENT';

          return (
            <button
              key={cfg.id}
              type="button"
              ref={(el) => {
                pinRefs.current[cfg.id] = el;
              }}
              onClick={() => onSelectRoom(cfg.id)}
              className="absolute top-0 left-0 transition-opacity duration-150"
              style={{ opacity: 0, willChange: 'transform' }}
            >
              <div
                className={`px-3 py-1.5 rounded-full shadow-lg flex items-center gap-2 text-xs font-medium backdrop-blur-md border transition ${
                  isIncident
                    ? 'bg-red-600 text-white border-red-400 animate-bounce'
                    : isSelected
                    ? 'bg-blue-600 text-white border-blue-400'
                    : 'bg-white/95 text-slate-800 border-slate-200'
                }`}
              >
                <span
                  className={`h-2 w-2 rounded-full ${
                    isIncident ? 'bg-white animate-ping' : 'bg-emerald-300'
                  }`}
                />
                <span className="font-semibold whitespace-nowrap">{cfg.name}</span>
                {telem && (
                  <span className="opacity-90 tnum font-mono text-[11px]">
                    {telem.temperature.toFixed(1)}°C
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* Top-Left: Clean Selected Room Pill */}
      {selectedRoomObj && (
        <div className="absolute top-4 left-4 z-20 pointer-events-none">
          <div
            className={`px-3.5 py-2 rounded-xl backdrop-blur-md border shadow-sm flex items-center gap-2.5 text-xs ${
              theme === 'daylight'
                ? 'bg-white/90 border-slate-200/90 text-slate-800'
                : 'bg-slate-900/85 border-white/10 text-slate-100'
            }`}
          >
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                selectedRoomObj.state === 'INCIDENT'
                  ? 'bg-red-500 animate-ping'
                  : selectedRoomObj.state === 'ANOMALY' || selectedRoomObj.state === 'ATTENTION'
                  ? 'bg-amber-500'
                  : 'bg-emerald-500'
              }`}
            />
            <span className="font-semibold">{selectedRoomObj.name}</span>
            <span className="opacity-50">•</span>
            <span className="opacity-75">Floor {selectedRoomObj.floor}</span>
          </div>
        </div>
      )}

      {/* Top-Right: Simple Floor & Split Controls */}
      <div className="absolute top-4 right-4 z-20 flex items-center gap-2">
        <div
          className={`flex items-center p-1 rounded-xl backdrop-blur-md border shadow-sm text-xs font-medium ${
            theme === 'daylight'
              ? 'bg-white/90 border-slate-200/90 text-slate-600'
              : 'bg-slate-900/85 border-white/10 text-slate-300'
          }`}
        >
          {(['all', 1, 2] as const).map((fl) => (
            <button
              key={String(fl)}
              type="button"
              onClick={() => setFloorFilter(fl)}
              className={`px-2.5 py-1 rounded-lg transition ${
                floorFilter === fl
                  ? 'bg-blue-600 text-white font-semibold shadow-sm'
                  : 'hover:opacity-80'
              }`}
            >
              {fl === 'all' ? 'All Floors' : `Floor ${fl}`}
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={() => setSplitFloors(!splitFloors)}
          className={`px-3 py-1.5 rounded-xl backdrop-blur-md border shadow-sm text-xs font-medium flex items-center gap-1.5 transition ${
            splitFloors
              ? 'bg-blue-600 text-white border-blue-500'
              : theme === 'daylight'
              ? 'bg-white/90 border-slate-200/90 text-slate-700 hover:bg-white'
              : 'bg-slate-900/85 border-white/10 text-slate-200 hover:bg-slate-800'
          }`}
          title="Separate Floor 2 from Floor 1 to see inside ground floor rooms"
        >
          <Layers className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">{splitFloors ? 'Floors Split' : 'Split Floors'}</span>
        </button>

        <button
          type="button"
          onClick={handleResetCamera}
          className={`p-2 rounded-xl backdrop-blur-md border shadow-sm transition ${
            theme === 'daylight'
              ? 'bg-white/90 border-slate-200/90 text-slate-700 hover:bg-white'
              : 'bg-slate-900/85 border-white/10 text-slate-200 hover:bg-slate-800'
          }`}
          title="Reset 3D camera angle"
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Bottom Legend & Help Hint */}
      <div className="absolute bottom-3 left-4 right-4 z-20 pointer-events-none flex items-center justify-between text-[11px]">
        <div
          className={`px-3 py-1.5 rounded-lg backdrop-blur-md border flex items-center gap-3 ${
            theme === 'daylight'
              ? 'bg-white/85 border-slate-200/80 text-slate-600'
              : 'bg-slate-900/80 border-white/10 text-slate-300'
          }`}
        >
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-500" /> Normal
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-amber-500" /> Warning
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-red-500" /> Alert
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-blue-600" /> Selected
          </span>
        </div>

        <span
          className={`hidden sm:inline px-2.5 py-1 rounded-lg backdrop-blur-md border ${
            theme === 'daylight'
              ? 'bg-white/80 border-slate-200/70 text-slate-500'
              : 'bg-slate-900/75 border-white/10 text-slate-400'
          }`}
        >
          Click any room to inspect • Drag to rotate • Scroll to zoom
        </span>
      </div>
    </div>
  );
}
