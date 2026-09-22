'use client';

import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { RefreshCw } from 'lucide-react';

export interface RoomState {
  id: string;
  name: string;
  floor: number;
  type: string;
  state: string; // NORMAL, ATTENTION, ANOMALY, INCIDENT, OFFLINE
}

interface Building3DProps {
  rooms: RoomState[];
  selectedRoomId: string | null;
  onSelectRoom: (roomId: string) => void;
}

export default function Building3D({ rooms, selectedRoomId, onSelectRoom }: Building3DProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const [hoveredRoom, setHoveredRoom] = useState<string | null>(null);
  const [activeFloorFilter, setActiveFloorFilter] = useState<'all' | 1 | 2>('all');

  // Recenter Camera action
  const handleRecenter = () => {
    if (cameraRef.current) {
      cameraRef.current.position.set(24, 22, 28);
      cameraRef.current.lookAt(0, 2, 0);
    }
  };

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    // 1. Scene & Camera
    const width = mount.clientWidth;
    const height = mount.clientHeight;
    const scene = new THREE.Scene();
    scene.background = null;
    scene.fog = new THREE.FogExp2(0x090d16, 0.016);

    const camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 1000);
    camera.position.set(24, 22, 28);
    camera.lookAt(0, 2, 0);
    cameraRef.current = camera;

    // 2. High-Performance WebGL Renderer
    const renderer = new THREE.WebGLRenderer({ 
      antialias: true, 
      alpha: true, 
      powerPreference: "high-performance" 
    });
    renderer.setSize(width, height);
    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    mount.appendChild(renderer.domElement);

    // 3. Balanced Natural Studio Lighting (Not overwhelming cyan)
    const ambientLight = new THREE.AmbientLight(0xf1f5f9, 0.7);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 1.1);
    dirLight.position.set(22, 35, 22);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 1024;
    dirLight.shadow.mapSize.height = 1024;
    dirLight.shadow.bias = -0.001;
    scene.add(dirLight);

    const rimLight = new THREE.DirectionalLight(0x94a3b8, 0.4);
    rimLight.position.set(-20, 15, -20);
    scene.add(rimLight);

    // Grid Floor
    const gridHelper = new THREE.GridHelper(50, 50, 0x334155, 0x1e293b);
    gridHelper.position.y = -0.05;
    scene.add(gridHelper);

    // Ground Plane with matte roughness
    const groundGeo = new THREE.PlaneGeometry(70, 70);
    const groundMat = new THREE.MeshStandardMaterial({ 
      color: 0x090d16, 
      roughness: 0.9, 
      metalness: 0.1 
    });
    const ground = new THREE.Mesh(groundGeo, groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);

    // Floor 2 Divider Holographic Grid
    const floor2Geo = new THREE.PlaneGeometry(28, 22);
    const floor2Mat = new THREE.MeshBasicMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.035,
      side: THREE.DoubleSide
    });
    const floor2Plate = new THREE.Mesh(floor2Geo, floor2Mat);
    floor2Plate.rotation.x = -Math.PI / 2;
    floor2Plate.position.set(0, 3.8, 0);
    scene.add(floor2Plate);

    // 4. Room Configurations (matching facility architecture)
    const roomConfigs = [
      { id: "entrance", name: "Main Entrance", x: 0, y: 1.5, z: 4, w: 8, h: 3, d: 5, floor: 1 },
      { id: "main_hall", name: "Main Hall & Atrium", x: 0, y: 1.5, z: -3, w: 12, h: 3, d: 7, floor: 1 },
      { id: "classroom_01", name: "Classroom 01", x: -8, y: 1.5, z: -3, w: 6, h: 3, d: 6, floor: 1 },
      { id: "classroom_02", name: "Classroom 02", x: 8, y: 1.5, z: -3, w: 6, h: 3, d: 6, floor: 1 },
      { id: "server_room", name: "Server Room", x: -8, y: 1.5, z: 4, w: 5, h: 3, d: 4, floor: 1 },
      { id: "emergency_exit", name: "Emergency Exit", x: 8, y: 1.5, z: 4, w: 5, h: 3, d: 4, floor: 1 },
      { id: "lab_01", name: "Computer Lab 01", x: -8, y: 5.5, z: -3, w: 6, h: 3, d: 6, floor: 2 },
      { id: "lab_02", name: "Chemistry Lab 02", x: 8, y: 5.5, z: -3, w: 6, h: 3, d: 6, floor: 2 },
      { id: "storage_room", name: "Chemical Storage", x: 0, y: 5.5, z: -4, w: 6, h: 3, d: 5, floor: 2 }
    ];

    const roomMeshes: { 
      [id: string]: { 
        mesh: THREE.Mesh; 
        wireframe: THREE.LineSegments; 
        beacon?: THREE.Mesh;
        floor: number;
      } 
    } = {};
    const interactiveObjects: THREE.Object3D[] = [];

    roomConfigs.forEach((cfg) => {
      const geo = new THREE.BoxGeometry(cfg.w - 0.25, cfg.h, cfg.d - 0.25);
      
      const mat = new THREE.MeshStandardMaterial({
        color: 0x10b981,
        transparent: true,
        opacity: 0.32,
        roughness: 0.2,
        metalness: 0.7
      });

      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.set(cfg.x, cfg.y, cfg.z);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.userData = { roomId: cfg.id, name: cfg.name, floor: cfg.floor };
      scene.add(mesh);
      interactiveObjects.push(mesh);

      // Wireframe contour
      const edges = new THREE.EdgesGeometry(geo);
      const wireMat = new THREE.LineBasicMaterial({ 
        color: 0x34d399, 
        linewidth: 1.5, 
        transparent: true, 
        opacity: 0.75 
      });
      const wireframe = new THREE.LineSegments(edges, wireMat);
      wireframe.position.copy(mesh.position);
      scene.add(wireframe);

      // Floating Sensor Beacon Indicator
      const beaconGeo = new THREE.SphereGeometry(0.24, 16, 16);
      const beaconMat = new THREE.MeshBasicMaterial({ color: 0x10b981 });
      const beacon = new THREE.Mesh(beaconGeo, beaconMat);
      beacon.position.set(cfg.x, cfg.y + cfg.h / 2 + 0.45, cfg.z);
      scene.add(beacon);

      roomMeshes[cfg.id] = { mesh, wireframe, beacon, floor: cfg.floor };
    });

    // Raycasting & Interaction
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const onPointerMove = (e: MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(interactiveObjects);
      if (intersects.length > 0) {
        const hitId = intersects[0].object.userData.roomId;
        setHoveredRoom(hitId);
        mount.style.cursor = 'pointer';
      } else {
        setHoveredRoom(null);
        mount.style.cursor = 'default';
      }
    };

    const onClick = (e: MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(interactiveObjects);
      if (intersects.length > 0) {
        const hitId = intersects[0].object.userData.roomId;
        onSelectRoom(hitId);
      }
    };

    mount.addEventListener('mousemove', onPointerMove);
    mount.addEventListener('click', onClick);

    // Animation Loop
    let animationFrameId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      const time = clock.getElapsedTime();

      // Dynamic color & opacity updates based on room telemetry states
      rooms.forEach((r) => {
        const obj = roomMeshes[r.id];
        if (!obj) return;

        let color = 0x10b981; // NORMAL: Emerald
        let wireColor = 0x34d399;
        let opacity = 0.32;

        if (r.state === 'INCIDENT') {
          // Strobe emergency alarm
          const strobe = (Math.sin(time * 8) + 1) / 2;
          color = strobe > 0.45 ? 0xef4444 : 0x7f1d1d;
          wireColor = 0xf87171;
          opacity = 0.7 + 0.2 * strobe;
        } else if (r.state === 'ANOMALY') {
          color = 0xf97316; // Orange
          wireColor = 0xfba34c;
          opacity = 0.55;
        } else if (r.state === 'ATTENTION') {
          color = 0xf59e0b; // Amber
          wireColor = 0xfde047;
          opacity = 0.45;
        } else if (r.state === 'OFFLINE') {
          color = 0x475569; // Slate
          wireColor = 0x64748b;
          opacity = 0.18;
        }

        // Selected room highlight
        if (r.id === selectedRoomId) {
          wireColor = 0x38bdf8; // Sky blue contour
          opacity = Math.min(0.9, opacity + 0.22);
        }

        // Floor filtering opacity dim
        if (activeFloorFilter !== 'all' && obj.floor !== activeFloorFilter) {
          opacity *= 0.2;
        }

        (obj.mesh.material as THREE.MeshStandardMaterial).color.setHex(color);
        (obj.mesh.material as THREE.MeshStandardMaterial).opacity = opacity;
        (obj.wireframe.material as THREE.LineBasicMaterial).color.setHex(wireColor);

        // Animate floating beacons
        if (obj.beacon) {
          obj.beacon.position.y = (r.floor === 2 ? 7.2 : 3.2) + Math.sin(time * 3 + (r.floor * 2)) * 0.15;
          (obj.beacon.material as THREE.MeshBasicMaterial).color.setHex(color);
        }
      });

      // Subtle atmospheric orbital oscillation
      scene.rotation.y = Math.sin(time * 0.06) * 0.12;

      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      if (!mount) return;
      const w = mount.clientWidth;
      const h = mount.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animationFrameId);
      mount.removeEventListener('mousemove', onPointerMove);
      mount.removeEventListener('click', onClick);
      window.removeEventListener('resize', handleResize);
      if (mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, [rooms, selectedRoomId, activeFloorFilter]);

  const focusedRoomObj = rooms.find(r => r.id === (hoveredRoom || selectedRoomId));

  return (
    <div className="relative w-full h-full min-h-[440px] rounded-2xl overflow-hidden bg-[#090d16] border border-white/[0.08] shadow-2xl">
      <div ref={mountRef} className="w-full h-full" />
      
      {/* Top Left: Clean Title Header (NO OVERLAP) */}
      <div className="absolute top-3.5 left-4 pointer-events-none flex items-center gap-2.5 z-10">
        <div className="flex items-center gap-2 bg-slate-900/85 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 text-xs font-mono shadow-md">
          <span className="h-2 w-2 rounded-full bg-emerald-400" />
          <span className="text-white font-bold tracking-wide">3D FACILITY TWIN</span>
          <span className="text-slate-600">|</span>
          <span className="text-slate-400 text-[11px]">2 FLOORS</span>
        </div>
      </div>

      {/* Top Right: Floor Filter Controls (NO OVERLAP) */}
      <div className="absolute top-3.5 right-4 z-10 flex items-center gap-1 bg-slate-900/85 backdrop-blur-md p-1 rounded-lg border border-white/10 text-[11px] font-mono shadow-md">
        <button
          type="button"
          onClick={() => setActiveFloorFilter('all')}
          className={`px-2.5 py-1 rounded-md transition ${
            activeFloorFilter === 'all' 
              ? 'bg-slate-800 text-white font-bold border border-white/15' 
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          All Floors
        </button>
        <button
          type="button"
          onClick={() => setActiveFloorFilter(1)}
          className={`px-2.5 py-1 rounded-md transition ${
            activeFloorFilter === 1 
              ? 'bg-slate-800 text-white font-bold border border-white/15' 
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Floor 1
        </button>
        <button
          type="button"
          onClick={() => setActiveFloorFilter(2)}
          className={`px-2.5 py-1 rounded-md transition ${
            activeFloorFilter === 2 
              ? 'bg-slate-800 text-white font-bold border border-white/15' 
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Floor 2
        </button>
      </div>

      {/* Bottom Left: Focused Target Room Pill */}
      {focusedRoomObj && (
        <div className="absolute bottom-3.5 left-4 z-10 pointer-events-none flex items-center gap-2 bg-slate-900/90 backdrop-blur-md border border-white/10 px-3 py-1.5 rounded-lg text-xs font-mono shadow-md">
          <span className="text-slate-400">Target:</span>
          <span className="text-white font-bold">{focusedRoomObj.name}</span>
          <span className="text-slate-400 text-[11px]">(FL {focusedRoomObj.floor})</span>
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
            focusedRoomObj.state === 'INCIDENT' ? 'bg-rose-500/25 text-rose-300' :
            focusedRoomObj.state === 'ANOMALY' ? 'bg-orange-500/25 text-orange-300' :
            focusedRoomObj.state === 'ATTENTION' ? 'bg-amber-500/25 text-amber-300' : 'bg-emerald-500/20 text-emerald-300'
          }`}>
            {focusedRoomObj.state}
          </span>
        </div>
      )}

      {/* Bottom Right: Clean Legend + Recenter Button (NO OVERLAP) */}
      <div className="absolute bottom-3.5 right-4 z-10 flex items-center gap-2">
        {/* Status legend */}
        <div className="hidden sm:flex items-center gap-3 bg-slate-900/90 backdrop-blur-md border border-white/10 px-3 py-1.5 rounded-lg text-[10px] font-mono shadow-md">
          <div className="flex items-center gap-1.5 text-slate-300">
            <span className="h-2 w-2 rounded-full bg-emerald-400" /> Normal
          </div>
          <div className="flex items-center gap-1.5 text-slate-300">
            <span className="h-2 w-2 rounded-full bg-amber-400" /> Attn
          </div>
          <div className="flex items-center gap-1.5 text-slate-300">
            <span className="h-2 w-2 rounded-full bg-orange-400" /> Anomaly
          </div>
          <div className="flex items-center gap-1.5 text-rose-300 font-bold">
            <span className="h-2 w-2 rounded-full bg-rose-500 animate-pulse" /> Incident
          </div>
        </div>

        {/* Recenter Camera button */}
        <button
          type="button"
          onClick={handleRecenter}
          className="bg-slate-900/90 hover:bg-slate-800 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 text-xs font-mono text-slate-300 hover:text-white flex items-center gap-1.5 transition shadow-md"
          title="Recenter camera to nominal viewpoint"
        >
          <RefreshCw className="h-3 w-3 text-cyan-400" />
          <span className="font-medium">Recenter</span>
        </button>
      </div>
    </div>
  );
}
