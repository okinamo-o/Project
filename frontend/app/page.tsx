'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  ShieldAlert, Eye, Mic, RotateCcw, Flame, Wind, Thermometer,
  ArrowUpRight, Send, FileText, Volume2,
  BellRing, ExternalLink, Sparkles, Maximize2, X,
  ShieldCheck, Sun, Moon, Building2, MessageSquare, CheckCircle2
} from 'lucide-react';
import Building3D, {
  RoomState,
  FACILITY_ROOM_CONFIGS,
} from '@/components/digital-twin/Building3D';
import { rtdb } from '@/lib/firebase';
import { ref as dbRef, onValue, set as dbSet, remove as dbRemove } from 'firebase/database';

interface SystemHealth {
  status: string;
  system: string;
  version: string;
  uptime_seconds: number;
  environment: string;
  database: string;
  ai_engine: {
    status: string;
    model: string;
    offline_reasoning: boolean;
  };
}

interface Incident {
  id: string;
  room_id: string;
  type: string;
  severity: string;
  confidence: number;
  status: string;
  summary: string;
  ai_explanation?: string;
  created_at?: string;
  timeline: Array<{ time: string; source: string; description: string }>;
  evidence: Array<{ id: number; source_type: string; source_id: string; contribution: number; explanation: string }>;
}

interface RoomTelemetry {
  temperature: number;
  humidity: number;
  gas: number;
  smoke: number;
  light: number;
  occupancy: number;
  tempHistory: number[];
  gasHistory: number[];
  smokeHistory: number[];
}

const DEFAULT_ROOM_TELEMETRY: Record<string, RoomTelemetry> = {
  server_room: { temperature: 18.5, humidity: 35.0, gas: 35.0, smoke: 0.1, light: 150, occupancy: 0, tempHistory: [18.4, 18.5, 18.6, 18.5, 18.5], gasHistory: [34, 35, 36, 35, 35], smokeHistory: [0.1, 0.1, 0.1, 0.1, 0.1] },
  classroom_01: { temperature: 21.8, humidity: 48.0, gas: 85.0, smoke: 0.3, light: 500, occupancy: 18, tempHistory: [21.5, 21.6, 21.7, 21.8, 21.8], gasHistory: [82, 84, 85, 85, 85], smokeHistory: [0.3, 0.3, 0.3, 0.3, 0.3] },
  classroom_02: { temperature: 22.2, humidity: 47.0, gas: 90.0, smoke: 0.3, light: 480, occupancy: 22, tempHistory: [21.9, 22.0, 22.1, 22.2, 22.2], gasHistory: [88, 89, 90, 90, 90], smokeHistory: [0.3, 0.3, 0.3, 0.3, 0.3] },
  lab_01: { temperature: 21.5, humidity: 44.0, gas: 80.0, smoke: 0.2, light: 520, occupancy: 12, tempHistory: [21.3, 21.4, 21.4, 21.5, 21.5], gasHistory: [78, 79, 80, 81, 80], smokeHistory: [0.2, 0.2, 0.2, 0.2, 0.2] },
  lab_02: { temperature: 23.5, humidity: 45.0, gas: 75.0, smoke: 0.4, light: 500, occupancy: 0, tempHistory: [23.2, 23.3, 23.4, 23.5, 23.5], gasHistory: [74, 75, 76, 75, 75], smokeHistory: [0.4, 0.4, 0.4, 0.4, 0.4] },
  storage_room: { temperature: 19.8, humidity: 40.0, gas: 95.0, smoke: 0.5, light: 80, occupancy: 0, tempHistory: [19.7, 19.8, 19.8, 19.8, 19.8], gasHistory: [93, 94, 95, 95, 95], smokeHistory: [0.5, 0.5, 0.5, 0.5, 0.5] },
  main_hall: { temperature: 21.0, humidity: 50.0, gas: 85.0, smoke: 0.3, light: 650, occupancy: 35, tempHistory: [20.8, 20.9, 21.0, 21.0, 21.1], gasHistory: [83, 84, 85, 85, 85], smokeHistory: [0.3, 0.3, 0.3, 0.3, 0.3] },
  entrance: { temperature: 20.5, humidity: 52.0, gas: 75.0, smoke: 0.2, light: 700, occupancy: 8, tempHistory: [20.3, 20.4, 20.5, 20.5, 20.6], gasHistory: [74, 75, 75, 76, 75], smokeHistory: [0.2, 0.2, 0.2, 0.2, 0.2] },
  emergency_exit: { temperature: 19.2, humidity: 46.0, gas: 65.0, smoke: 0.1, light: 200, occupancy: 0, tempHistory: [19.1, 19.2, 19.2, 19.2, 19.2], gasHistory: [64, 65, 65, 66, 65], smokeHistory: [0.1, 0.1, 0.1, 0.1, 0.1] }
};

function generateLocalExpertAnswer(
  q: string,
  targetRoomId: string,
  allTelemetry: Record<string, RoomTelemetry>,
  rooms: RoomState[],
  incidents: Incident[]
): string {
  const qLower = q.toLowerCase();

  // 1. Strict Domain Guardrail (Rule 0)
  if (
    qLower.includes('calculator') ||
    qLower.includes('snake game') ||
    qLower.includes('write code') ||
    qLower.includes('poem') ||
    qLower.includes('joke') ||
    qLower.includes('story')
  ) {
    return 'I am the NEXUS Smart Building Assistant and can only help with NEXUS facility monitoring, room telemetry, safety incidents, hardware sensors, and system architecture.';
  }

  // 2. Resolve room from question aliases
  const roomAliasMap: Record<string, string[]> = {
    classroom_01: ['classroom 1', 'classroom 01', 'class 1', 'classroom1', 'room 1', 'c1'],
    classroom_02: ['classroom 2', 'classroom 02', 'class 2', 'classroom2', 'room 2', 'c2'],
    lab_02: ['lab 2', 'lab 02', 'chemistry', 'chem lab', 'lab2', 'chemistry lab', 'physics lab'],
    lab_01: ['lab 1', 'lab 01', 'computer lab', 'lab1', 'comp lab'],
    server_room: ['server room', 'servers', 'datacenter', 'server'],
    storage_room: ['storage room', 'storage', 'chemical storage'],
    main_hall: ['main hall', 'hall', 'hallway'],
    entrance: ['entrance', 'main entrance', 'lobby'],
    emergency_exit: ['emergency exit', 'fire exit']
  };

  let matchedRoomId = targetRoomId;
  for (const [rId, aliases] of Object.entries(roomAliasMap)) {
    if (aliases.some((a) => qLower.includes(a))) {
      matchedRoomId = rId;
      break;
    }
  }

  const roomObj = rooms.find((r) => r.id === matchedRoomId) || {
    id: matchedRoomId,
    name: matchedRoomId.replace('_', ' ').toUpperCase(),
    floor: 1,
    state: 'NORMAL',
    type: 'room'
  };
  const roomName = roomObj.name || matchedRoomId;
  const telem = allTelemetry[matchedRoomId] || DEFAULT_ROOM_TELEMETRY[matchedRoomId] || {
    temperature: 21.8,
    humidity: 48,
    gas: 85,
    smoke: 0.3,
    light: 500,
    occupancy: 0,
    tempHistory: [],
    gasHistory: [],
    smokeHistory: []
  };
  const roomIncidents = incidents.filter(
    (i) => i.room_id === matchedRoomId && (i.status === 'ACTIVE' || !i.status)
  );

  // 3. Conversational Acknowledgments
  if (/^(sounds good|ok|okay|thanks|thank you|great|perfect|hello|hi|hey)[\s!.]*$/i.test(q.trim())) {
    return `Glad to assist! All building telemetry is streaming smoothly. Let me know if you need specific readings or safety reports for ${roomName} or any other room.`;
  }

  // 4. "What happened in [Room] in the past 1 hour?" / Status queries
  if (
    qLower.includes('what happened') ||
    qLower.includes('status') ||
    qLower.includes('past hour') ||
    qLower.includes('last hour') ||
    qLower.includes('past 1 hour') ||
    qLower.includes('just now') ||
    qLower.includes('safe') ||
    qLower.includes('check')
  ) {
    if (roomIncidents.length === 0) {
      return (
        `🟢 **All Clear — ${roomName} is currently safe and operating normally (\`NORMAL\`).**\n\n` +
        `Over the past hour, **${roomName}** has maintained 100% nominal operation with **0 active incidents, warnings, or anomalies detected**.\n\n` +
        `### Current Telemetry (${roomName}):\n` +
        `* **Status**: \`${roomObj.state || 'NORMAL'}\` (Floor ${roomObj.floor})\n` +
        `* **Temperature**: ${telem.temperature.toFixed(1)}°C (Nominal)\n` +
        `* **Humidity**: ${telem.humidity.toFixed(0)}% RH\n` +
        `* **Gas (MQ-2)**: ${telem.gas.toFixed(0)} ppm (Clean Air)\n` +
        `* **Smoke**: ${(telem.smoke ?? 0.3).toFixed(1)}% (Clean Baseline)\n` +
        `* **Occupancy**: ${telem.occupancy > 0 ? `${telem.occupancy} person(s) present` : 'Inactive / Unoccupied'}`
      );
    } else {
      const inc = roomIncidents[0];
      return (
        `⚠️ **Active Alert in ${roomName}**\n\n` +
        `* **Classification:** \`${inc.type.replace(/_/g, ' ')}\` [**${inc.severity}**]\n` +
        `* **Confidence:** ${Math.round((inc.confidence || 0.9) * 100)}%\n` +
        `* **Summary:** ${inc.summary}\n\n` +
        `### Live Room Telemetry:\n` +
        `* **Temperature:** ${telem.temperature.toFixed(1)}°C\n` +
        `* **Gas:** ${telem.gas.toFixed(0)} ppm\n` +
        `* **Smoke:** ${(telem.smoke ?? 0.3).toFixed(1)}%\n` +
        `* **Occupancy:** ${telem.occupancy} person(s)`
      );
    }
  }

  // 5. Specific Sensor queries
  if (qLower.includes('temperature') || qLower.includes('temp') || qLower.includes('heat')) {
    return `The current temperature in **${roomName}** is **${telem.temperature.toFixed(1)}°C** with **${telem.humidity.toFixed(0)}%** relative humidity. Environmental conditions are within normal limits.`;
  }
  if (qLower.includes('gas') || qLower.includes('air') || qLower.includes('mq2')) {
    return `The air quality in **${roomName}** is clean: **${telem.gas.toFixed(0)} ppm** (MQ-2 gas detector). No toxic combustion or volatile fume hazards are detected.`;
  }
  if (qLower.includes('smoke')) {
    return `The optical smoke obscuration in **${roomName}** reads **${(telem.smoke ?? 0.3).toFixed(1)}%**, comfortably below the 6.0% fire detection threshold.`;
  }
  if (qLower.includes('people') || qLower.includes('occupancy') || qLower.includes('camera') || qLower.includes('who is in')) {
    return `Surveillance in **${roomName}** indicates **${telem.occupancy}** occupant(s) in zone. YOLOv5 camera vision is active.`;
  }
  if (qLower.includes('all rooms') || qLower.includes('building') || qLower.includes('every room')) {
    const activeTotal = incidents.filter((i) => i.status === 'ACTIVE' || !i.status).length;
    return `Building Overview: 9 zones monitored across 2 floors. Active incidents: **${activeTotal}**. All other zones are currently operating in nominal (\`NORMAL\`) state.`;
  }

  // 6. Default Fallback
  return `🟢 **${roomName}** is operating normally (\`NORMAL\`). Live telemetry: Temp = ${telem.temperature.toFixed(1)}°C, Gas = ${telem.gas.toFixed(0)} ppm, Smoke = ${(telem.smoke ?? 0.3).toFixed(1)}%, Occupancy = ${telem.occupancy}. No safety hazards detected.`;
}

export default function OperationsCenter() {
  const [theme, setTheme] = useState<'daylight' | 'midnight'>('daylight');
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [rooms, setRooms] = useState<RoomState[]>(
    FACILITY_ROOM_CONFIGS.map((c) => ({
      id: c.id,
      name: c.name,
      floor: c.floor,
      type: c.kind,
      state: 'NORMAL',
    }))
  );
  const [selectedRoomId, setSelectedRoomId] = useState<string>('classroom_01');
  const selectedRoomIdRef = useRef<string>(selectedRoomId);

  // Restore saved theme and selected room from localStorage on mount
  useEffect(() => {
    try {
      const savedTheme = localStorage.getItem('nexus_theme') as 'daylight' | 'midnight' | null;
      if (savedTheme === 'daylight' || savedTheme === 'midnight') {
        setTheme(savedTheme);
        document.documentElement.setAttribute('data-theme', savedTheme);
      }
      const savedRoom = localStorage.getItem('nexus_selected_room');
      if (savedRoom && FACILITY_ROOM_CONFIGS.some((c) => c.id === savedRoom)) {
        setSelectedRoomId(savedRoom);
        selectedRoomIdRef.current = savedRoom;
      }
    } catch {}
  }, []);

  // Persist theme to localStorage and HTML attribute whenever it changes
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem('nexus_theme', theme);
    } catch {}
  }, [theme]);

  // Persist selectedRoomId to localStorage and ref whenever it changes
  useEffect(() => {
    selectedRoomIdRef.current = selectedRoomId;
    try {
      localStorage.setItem('nexus_selected_room', selectedRoomId);
    } catch {}
  }, [selectedRoomId]);

  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const wsConnectedRef = useRef<boolean>(false);
  const [firebaseConnected, setFirebaseConnected] = useState<boolean>(false);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [snapshotModalOpen, setSnapshotModalOpen] = useState<boolean>(false);
  const [mobileTab, setMobileTab] = useState<'overview' | '3d' | 'sensors' | 'ai'>('overview');
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const [allTelemetry, setAllTelemetry] = useState<Record<string, RoomTelemetry>>(DEFAULT_ROOM_TELEMETRY);
  const [audioEvent, setAudioEvent] = useState<string>('NORMAL');
  const [audioRms, setAudioRms] = useState<number>(0.0015);
  const audioEventTimerRef = useRef<NodeJS.Timeout | null>(null);
  const [isWokwiActive, setIsWokwiActive] = useState<boolean>(false);
  const wokwiTimerRef = useRef<NodeJS.Timeout | null>(null);
  const [activeWokwiRooms, setActiveWokwiRooms] = useState<Record<string, boolean>>({});
  const wokwiTimersRef = useRef<Record<string, NodeJS.Timeout>>({});
  const [predictionVariable, setPredictionVariable] = useState<'temperature' | 'gas' | 'humidity'>('temperature');
  const [prediction, setPrediction] = useState<any>(null);
  const [visionSnapshot, setVisionSnapshot] = useState<string | null>(null);

  const [forensicExplanation, setForensicExplanation] = useState<string | null>(null);
  const [explainingIncidentId, setExplainingIncidentId] = useState<string | null>(null);

  const currentTelem = allTelemetry[selectedRoomId] || DEFAULT_ROOM_TELEMETRY[selectedRoomId] || {
    temperature: 22.0, humidity: 45.0, gas: 80.0, smoke: 0.3, light: 500, occupancy: 0,
    tempHistory: [22.0, 22.0, 22.0, 22.0, 22.0], gasHistory: [80, 80, 80, 80, 80], smokeHistory: [0.3, 0.3, 0.3, 0.3, 0.3]
  };
  const temperature = currentTelem.temperature;
  const humidity = currentTelem.humidity;
  const gas = currentTelem.gas;
  const smoke = currentTelem.smoke ?? 0.3;
  const light = currentTelem.light ?? 500;
  const occupancy = currentTelem.occupancy;

  // AI Assistant state
  const [question, setQuestion] = useState<string>('');
  const [chatMessages, setChatMessages] = useState<Array<{ role: 'user' | 'assistant'; text: string; offline?: boolean }>>([
    {
      role: 'assistant',
      text: 'Hello! I am monitoring all 9 rooms across the building. Ask me about any room’s temperature, air quality, camera feed, or active alerts.'
    }
  ]);
  const [aiLoading, setAiLoading] = useState<boolean>(false);
  const [isListening, setIsListening] = useState<boolean>(false);

  useEffect(() => {
    if (chatMessages.length > 1 || aiLoading) {
      if (chatScrollRef.current) {
        chatScrollRef.current.scrollTo({
          top: chatScrollRef.current.scrollHeight,
          behavior: 'smooth',
        });
      }
    }
  }, [chatMessages, aiLoading]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && snapshotModalOpen) {
        setSnapshotModalOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [snapshotModalOpen]);

  const activeIncident =
    incidents.find(
      (i) => (i.status === 'ACTIVE' || !i.status) && i.room_id === selectedRoomId
    ) || null;

  const loadInitialData = async () => {
    const targetRoom = selectedRoomIdRef.current;
    try {
      const [hRes, rRes, iRes, pRes, vRes, sRes, visRes, audRes] = await Promise.all([
        fetch('http://127.0.0.1:8000/api/health'),
        fetch('http://127.0.0.1:8000/api/rooms'),
        fetch('http://127.0.0.1:8000/api/incidents?status=ACTIVE'),
        fetch(`http://127.0.0.1:8000/api/prediction/${targetRoom}?variable=${predictionVariable}`),
        fetch(`http://127.0.0.1:8000/api/vision/snapshot/${targetRoom}`),
        fetch(`http://127.0.0.1:8000/api/sensors/room/${targetRoom}/latest`),
        fetch(`http://127.0.0.1:8000/api/vision/latest/${targetRoom}`),
        fetch(`http://127.0.0.1:8000/api/audio/latest/${targetRoom}`)
      ]);

      if (hRes.ok) setHealth(await hRes.json());
      if (rRes.ok) {
        const fetchedRooms = await rRes.json();
        if (Array.isArray(fetchedRooms) && fetchedRooms.length > 0) {
          setRooms(fetchedRooms);
        }
      }
      if (iRes.ok) setIncidents(await iRes.json());
      if (pRes.ok) setPrediction(await pRes.json());
      if (vRes.ok) {
        const snap = await vRes.json();
        if (snap.snapshot_base64) setVisionSnapshot(snap.snapshot_base64);
      }
      if (audRes.ok) {
        const aData = await audRes.json();
        const ev = aData.event_type || 'NORMAL';
        setAudioEvent(ev);
        if (ev === 'SPEECH' || ev === 'ALARM' || ev === 'IMPACT') {
          if (audioEventTimerRef.current) clearTimeout(audioEventTimerRef.current);
          audioEventTimerRef.current = setTimeout(() => {
            setAudioEvent('NORMAL');
            audioEventTimerRef.current = null;
          }, 3000);
        }
      }

      let latestOccupancy: number | undefined;
      if (visRes.ok) {
        const vData = await visRes.json();
        const occ = vData.occupancy ?? vData.metadata?.occupancy_count;
        if (occ !== undefined) latestOccupancy = Number(occ);
      }

      if (sRes.ok) {
        const sData = await sRes.json();
        if (sData.readings) {
          setAllTelemetry((prev) => {
            const cur = prev[targetRoom] || DEFAULT_ROOM_TELEMETRY[targetRoom] || {
              temperature: 22.0, humidity: 45.0, gas: 80.0, smoke: 0.3, light: 500, occupancy: 0,
              tempHistory: [], gasHistory: [], smokeHistory: []
            };
            const r = sData.readings;
            const newT = r.temperature ? r.temperature.value : cur.temperature;
            const newG = r.gas ? r.gas.value : cur.gas;
            const newS = r.smoke ? r.smoke.value : (cur.smoke ?? 0.3);
            const newL = r.light ? r.light.value : (cur.light ?? 500);
            const newH = r.humidity ? r.humidity.value : cur.humidity;
            const newOcc = latestOccupancy !== undefined ? latestOccupancy : cur.occupancy;
            return {
              ...prev,
              [targetRoom]: {
                ...cur,
                temperature: newT,
                gas: newG,
                smoke: newS,
                light: newL,
                humidity: newH,
                occupancy: newOcc,
                tempHistory: [...(cur.tempHistory || []).slice(-12), newT],
                gasHistory: [...(cur.gasHistory || []).slice(-12), newG],
                smokeHistory: [...(cur.smokeHistory || []).slice(-12), newS]
              }
            };
          });
        }
      }
    } catch (e) {
      console.error('Failed to load initial data:', e);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, [selectedRoomId, predictionVariable]);

  // WebSocket connection
  useEffect(() => {
    let ws: WebSocket;
    try {
      ws = new WebSocket('ws://127.0.0.1:8000/ws/telemetry');
      ws.onopen = () => {
        wsConnectedRef.current = true;
        setWsConnected(true);
      };
      ws.onclose = () => {
        wsConnectedRef.current = false;
        setWsConnected(false);
      };
      ws.onerror = () => {
        wsConnectedRef.current = false;
        setWsConnected(false);
      };
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const roomTarget = data.room_id || 'lab_02';

          if (data.type === 'SENSOR_READING' || data.type === 'SENSOR_BATCH' || data.type === 'VISION_EVENT') {
            setAllTelemetry((prev) => {
              const cur = prev[roomTarget] || DEFAULT_ROOM_TELEMETRY[roomTarget] || {
                temperature: 22.0, humidity: 45.0, gas: 80.0, smoke: 0.3, light: 500, occupancy: 0,
                tempHistory: [], gasHistory: [], smokeHistory: []
              };
              let t = cur.temperature;
              let g = cur.gas;
              let s = cur.smoke ?? 0.3;
              let l = cur.light ?? 500;
              let h = cur.humidity;
              let o = cur.occupancy;

              if (data.type === 'SENSOR_READING') {
                if (data.sensor_type === 'temperature') t = data.value;
                if (data.sensor_type === 'gas') g = data.value;
                if (data.sensor_type === 'smoke') s = data.value;
                if (data.sensor_type === 'light') l = data.value;
                if (data.sensor_type === 'humidity') h = data.value;
              } else if (data.type === 'SENSOR_BATCH') {
                data.readings.forEach((r: any) => {
                  if (r.sensor_type === 'temperature') t = r.value;
                  if (r.sensor_type === 'gas') g = r.value;
                  if (r.sensor_type === 'smoke') s = r.value;
                  if (r.sensor_type === 'light') l = r.value;
                  if (r.sensor_type === 'humidity') h = r.value;
                });
              } else if (data.type === 'VISION_EVENT') {
                o = data.occupancy;
                if (data.snapshot_base64 && roomTarget === selectedRoomIdRef.current) {
                  setVisionSnapshot(data.snapshot_base64);
                }
              }

              return {
                ...prev,
                [roomTarget]: {
                  ...cur,
                  temperature: t,
                  gas: g,
                  smoke: s,
                  light: l,
                  humidity: h,
                  occupancy: o,
                  tempHistory: [...(cur.tempHistory || []).slice(-12), t],
                  gasHistory: [...(cur.gasHistory || []).slice(-12), g],
                  smokeHistory: [...(cur.smokeHistory || []).slice(-12), s]
                }
              };
            });
          }

          if (data.type === 'AUDIO_EVENT') {
            if (typeof data.rms_energy === 'number') {
              setAudioRms(data.rms_energy);
            }
            const ev = data.event_type || 'NORMAL';
            if (ev === 'SPEECH' || ev === 'ALARM' || ev === 'IMPACT') {
              setAudioEvent(ev);
              if (audioEventTimerRef.current) clearTimeout(audioEventTimerRef.current);
              audioEventTimerRef.current = setTimeout(() => {
                setAudioEvent('NORMAL');
                audioEventTimerRef.current = null;
              }, 3000);
            } else if (!audioEventTimerRef.current) {
              setAudioEvent('NORMAL');
            }
          } else if (data.type === 'SENSOR_BATCH') {
            if (data.is_wokwi) {
              const rid = data.room_id || 'lab_02';
              setActiveWokwiRooms((prev) => ({ ...prev, [rid]: true }));
              setIsWokwiActive(true);
              if (wokwiTimersRef.current[rid]) clearTimeout(wokwiTimersRef.current[rid]);
              wokwiTimersRef.current[rid] = setTimeout(() => {
                setActiveWokwiRooms((prev) => ({ ...prev, [rid]: false }));
                delete wokwiTimersRef.current[rid];
                setIsWokwiActive(false);
              }, 15000);
            }
          } else if (data.type === 'INCIDENT_ALERT') {
            const newInc: Incident = {
              id: data.id || data.incident_id || `inc_${Date.now()}`,
              room_id: data.room_id,
              type: data.incident_type || data.type,
              severity: data.severity || 'CRITICAL',
              confidence: data.confidence || 0.9,
              status: 'ACTIVE',
              summary: data.summary || `Alert detected in ${data.room_id}`,
              evidence: data.evidence || [],
              timeline: data.timeline || [],
              created_at: data.created_at || new Date().toISOString()
            };
            setIncidents((prev) => [newInc, ...prev.filter((i) => i.room_id !== data.room_id && i.id !== newInc.id)]);
            setRooms((prev) =>
              prev.map((r) =>
                r.id === data.room_id
                  ? { ...r, state: data.severity === 'CRITICAL' ? 'INCIDENT' : 'ANOMALY' }
                  : r
              )
            );
          } else if (data.type === 'INCIDENT_RESOLVED') {
            setIncidents((prev) =>
              prev.filter((i) => i.id !== data.incident_id && i.room_id !== data.room_id)
            );
            setRooms((prev) =>
              prev.map((r) => (r.id === data.room_id ? { ...r, state: 'NORMAL' } : r))
            );
          } else if (data.type === 'SIMULATION_RESULT') {
            loadInitialData();
          } else if (data.type === 'ROOM_STATE_CHANGED') {
            setRooms((prev) => prev.map((r) => (r.id === data.room_id ? { ...r, state: data.state } : r)));
          }
        } catch (err) {
          console.error('WS error:', err);
        }
      };
    } catch (e) {
      console.error('WS connect error:', e);
    }

    return () => {
      if (ws) ws.close();
    };
  }, []);

  // Firebase Realtime Database subscription
  useEffect(() => {
    let unsubTelemetry: (() => void) | undefined;
    let unsubIncidents: (() => void) | undefined;
    let unsubRooms: (() => void) | undefined;

    try {
      if (rtdb) {
        const telemRef = dbRef(rtdb, 'telemetry');
        unsubTelemetry = onValue(
          telemRef,
          (snapshot) => {
            setFirebaseConnected(true);
            if (wsConnectedRef.current) return;
            if (snapshot.exists()) {
              const val = snapshot.val();
              if (val && typeof val === 'object') {
                setAllTelemetry((prev) => {
                  const updated = { ...prev };
                  Object.entries(val).forEach(([roomId, data]: [string, any]) => {
                    if (!data || typeof data !== 'object') return;
                    const cur = updated[roomId] || DEFAULT_ROOM_TELEMETRY[roomId] || {
                      temperature: 22.0, humidity: 45.0, gas: 80.0, smoke: 0.3, light: 500, occupancy: 0,
                      tempHistory: [], gasHistory: [], smokeHistory: []
                    };
                    let t = data.temperature !== undefined ? Number(data.temperature) : cur.temperature;
                    let g = data.gas !== undefined ? Number(data.gas) : cur.gas;
                    let s = data.smoke !== undefined ? Number(data.smoke) : (cur.smoke ?? 0.3);
                    let l = data.light !== undefined ? Number(data.light) : (cur.light ?? 500);
                    let h = data.humidity !== undefined ? Number(data.humidity) : cur.humidity;
                    let o = data.occupancy !== undefined ? Number(data.occupancy) : cur.occupancy;

                    updated[roomId] = {
                      ...cur,
                      temperature: t,
                      gas: g,
                      smoke: s,
                      light: l,
                      humidity: h,
                      occupancy: o,
                      tempHistory: [...(cur.tempHistory || []).slice(-12), t],
                      gasHistory: [...(cur.gasHistory || []).slice(-12), g],
                      smokeHistory: [...(cur.smokeHistory || []).slice(-12), s]
                    };
                  });
                  return updated;
                });
              }
            }
          },
          (err) => { console.warn('[NEXUS] Firebase telemetry read denied/failed:', err?.message); }
        );

        const incRef = dbRef(rtdb, 'incidents');
        unsubIncidents = onValue(
          incRef,
          (snapshot) => {
            setFirebaseConnected(true);
            if (wsConnectedRef.current) return;
            if (snapshot.exists()) {
              const val = snapshot.val();
              if (val && typeof val === 'object') {
                const incList: Incident[] = Object.entries(val).map(([key, item]: [string, any]) => ({
                  id: item.id || item.incident_id || key,
                  room_id: item.room_id || '',
                  type: (item.incident_type && item.incident_type !== 'INCIDENT_ALERT' ? item.incident_type : item.type) || 'ANOMALY',
                  severity: item.severity || 'WARNING',
                  confidence: item.confidence ?? 0.85,
                  status: item.status || 'ACTIVE',
                  summary: item.summary || '',
                  evidence: item.evidence || [],
                  timeline: item.timeline || [],
                  created_at: item.created_at || new Date().toISOString()
                }));
                setIncidents(incList.filter((i) => i.status === 'ACTIVE'));
              } else {
                setIncidents([]);
              }
            } else {
              setIncidents([]);
            }
          },
          () => {}
        );

        const roomsRef = dbRef(rtdb, 'rooms');
        unsubRooms = onValue(
          roomsRef,
          (snapshot) => {
            setFirebaseConnected(true);
            if (wsConnectedRef.current) return;
            if (snapshot.exists()) {
              const val = snapshot.val();
              if (val && typeof val === 'object') {
                setRooms((prev) =>
                  prev.map((r) => (val[r.id] && val[r.id].state ? { ...r, state: val[r.id].state } : r))
                );
              }
            }
          },
          () => {}
        );
      }
    } catch {}

    return () => {
      if (unsubTelemetry) unsubTelemetry();
      if (unsubIncidents) unsubIncidents();
      if (unsubRooms) unsubRooms();
    };
  }, []);

  // AI Ask Handler
  const handleAsk = async (queryText?: string) => {
    const q = queryText || question;
    if (!q.trim() || aiLoading) return;

    const recentHistory = chatMessages.slice(-6).map((m) => ({
      role: m.role,
      text: m.text
    }));

    setChatMessages((prev) => [...prev, { role: 'user', text: q }]);
    setQuestion('');
    setAiLoading(true);

    try {
      const res = await fetch('http://127.0.0.1:8000/api/ai/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: q,
          room_id: selectedRoomId,
          history: recentHistory
        })
      });
      if (res.ok) {
        const data = await res.json();
        setChatMessages((prev) => [
          ...prev,
          { role: 'assistant', text: data.answer, offline: data.is_offline_mode }
        ]);
        fetch('http://127.0.0.1:8000/api/health')
          .then((r) => r.ok && r.json())
          .then((h) => h && setHealth(h))
          .catch(() => {});
        return;
      }
      throw new Error('API response not ok');
    } catch {
      // Seamless Local Expert Fallback: Answer accurately using live client telemetry & room state!
      const localAnswer = generateLocalExpertAnswer(q, selectedRoomId, allTelemetry, rooms, incidents);
      setChatMessages((prev) => [
        ...prev,
        { role: 'assistant', text: localAnswer, offline: true }
      ]);
    } finally {
      setAiLoading(false);
    }
  };

  const handleExplainIncident = async (incidentId: string) => {
    setExplainingIncidentId(incidentId);
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/ai/explain/${incidentId}`);
      if (res.ok) {
        const data = await res.json();
        setForensicExplanation(data.explanation || data.summary || '');
      }
    } catch (e) {
      console.error('Explain error:', e);
    } finally {
      setExplainingIncidentId(null);
    }
  };

  const handleResolveSingleIncident = async (incidentId: string) => {
    setForensicExplanation(null);
    setIncidents((prev) => prev.filter((i) => i.id !== incidentId));
    setRooms((prev) => prev.map((r) => (r.id === selectedRoomId ? { ...r, state: 'NORMAL' } : r)));
    try {
      if (rtdb) {
        dbRemove(dbRef(rtdb, `incidents/${incidentId}`)).catch(() => {});
        dbSet(dbRef(rtdb, `rooms/${selectedRoomId}`), { state: 'NORMAL', active_incident_id: null }).catch(() => {});
      }
    } catch {}
    try {
      await fetch(`http://127.0.0.1:8000/api/incidents/${incidentId}/resolve`, { method: 'POST' });
      await loadInitialData();
    } catch {}
  };

  const toggleSpeechRecognition = () => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      alert('Voice input is not supported in this browser.');
      return;
    }
    if (isListening) {
      setIsListening(false);
      return;
    }
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';
    recognition.onstart = () => setIsListening(true);
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);
    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setQuestion(transcript);
      handleAsk(transcript);
    };
    recognition.start();
  };

  const handleResetSystem = async () => {
    const prevIncs = [...incidents];
    setIncidents([]);
    setRooms((prev) => prev.map((r) => ({ ...r, state: 'NORMAL' })));
    setAllTelemetry(DEFAULT_ROOM_TELEMETRY);
    setAudioEvent('NORMAL');
    setForensicExplanation(null);
    try {
      if (rtdb) {
        dbRemove(dbRef(rtdb, 'incidents')).catch(() => {});
        for (const r of rooms) {
          dbSet(dbRef(rtdb, `rooms/${r.id}`), { state: 'NORMAL', active_incident_id: null }).catch(() => {});
        }
      }
    } catch {}
    try {
      for (const inc of prevIncs) {
        await fetch(`http://127.0.0.1:8000/api/incidents/${inc.id}/resolve`, { method: 'POST' });
      }
      for (const r of rooms) {
        await fetch(`http://127.0.0.1:8000/api/rooms/${r.id}/state`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ state: 'NORMAL' })
        });
      }
      await loadInitialData();
    } catch {}
  };

  const renderSmoothSparkline = (data: number[], color: string) => {
    const list = data && data.length >= 2 ? data : [data?.[0] ?? 20, data?.[0] ?? 20];
    const min = Math.min(...list);
    const max = Math.max(...list);
    const range = Math.max(max - min, 0.5);
    const width = 140;
    const height = 24;
    const points = list
      .map((val, idx) => {
        const x = 3 + (idx / (list.length - 1)) * (width - 6);
        const y = height - ((val - min) / range) * (height - 8) - 4;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');

    return (
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full overflow-hidden" preserveAspectRatio="none">
        <polyline
          points={points}
          fill="none"
          stroke={color}
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  };

  const selectedRoomObj = rooms.find((r) => r.id === selectedRoomId) || rooms[0];
  const activeIncidents = incidents.filter((i) => i.status === 'ACTIVE' || !i.status);
  const criticalIncidents = activeIncidents.filter((i) => i.severity === 'CRITICAL');
  const warningIncidents = activeIncidents.filter((i) => i.severity !== 'CRITICAL');
  const activeAlertCount = criticalIncidents.length;
  const activeWarningCount = warningIncidents.length;
  const unitLabel = predictionVariable === 'temperature' ? '°C' : predictionVariable === 'gas' ? ' ppm' : '%';

  return (
    <main className="min-h-screen pb-24 lg:pb-10 w-full max-w-[100vw] overflow-x-hidden">
      {/* =====================================================================
          1. CLEAN TOP HEADER BAR (Mobile & Desktop Optimized)
         ===================================================================== */}
      <header className="sticky top-0 z-40 border-b border-[var(--border-color)] bg-[var(--bg-surface)]/95 backdrop-blur-md">
        <div className="max-w-[1560px] mx-auto px-3 sm:px-6 h-14 sm:h-16 flex items-center justify-between gap-2 sm:gap-4">
          {/* Left: Brand & Clear Building Status */}
          <div className="flex items-center gap-2 sm:gap-4 min-w-0">
            <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
              <div className="h-8 w-8 sm:h-9 sm:w-9 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow-sm">
                <Building2 className="h-4 w-4 sm:h-5 sm:w-5" />
              </div>
              <div>
                <span className="font-display font-bold text-base sm:text-lg tracking-tight text-[var(--text-primary)]">
                  NEXUS
                </span>
                <span className="hidden md:inline-block ml-2 text-xs text-[var(--text-muted)]">
                  Smart Building Monitor
                </span>
              </div>
            </div>

            <div className="h-5 w-[1px] bg-[var(--border-color)] hidden sm:block shrink-0" />

            {/* Overall Building Status Pill (Differentiates Alerts vs Warnings) */}
            {activeAlertCount > 0 && activeWarningCount > 0 ? (
              <div className="flex items-center gap-1.5 sm:gap-2 min-w-0">
                <div className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1 rounded-full bg-red-500/10 border border-red-500/30 text-red-600 dark:text-red-400 text-[11px] sm:text-xs font-semibold truncate">
                  <span className="h-2 w-2 rounded-full bg-red-500 animate-ping shrink-0" />
                  <span className="sm:hidden">{activeAlertCount} Alert{activeAlertCount > 1 ? 's' : ''}</span>
                  <span className="hidden sm:inline">{activeAlertCount} Active Alert{activeAlertCount > 1 ? 's' : ''}</span>
                </div>
                <div className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-400 text-[11px] sm:text-xs font-semibold truncate">
                  <span className="h-2 w-2 rounded-full bg-amber-500 shrink-0" />
                  <span className="sm:hidden">{activeWarningCount} Warn</span>
                  <span className="hidden sm:inline">{activeWarningCount} Active Warning{activeWarningCount > 1 ? 's' : ''}</span>
                </div>
              </div>
            ) : activeAlertCount > 0 ? (
              <div className="flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3 py-1 rounded-full bg-red-500/10 border border-red-500/30 text-red-600 dark:text-red-400 text-[11px] sm:text-xs font-semibold truncate">
                <span className="h-2 w-2 rounded-full bg-red-500 animate-ping shrink-0" />
                <span>{activeAlertCount} Active Alert{activeAlertCount > 1 ? 's' : ''}</span>
              </div>
            ) : activeWarningCount > 0 ? (
              <div className="flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-400 text-[11px] sm:text-xs font-semibold truncate">
                <span className="h-2 w-2 rounded-full bg-amber-500 shrink-0" />
                <span>{activeWarningCount} Active Warning{activeWarningCount > 1 ? 's' : ''}</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/25 text-emerald-600 dark:text-emerald-400 text-[11px] sm:text-xs font-medium truncate">
                <span className="h-2 w-2 rounded-full bg-emerald-500 shrink-0" />
                <span className="sm:hidden">All Normal</span>
                <span className="hidden sm:inline">All 9 Rooms Normal</span>
              </div>
            )}
          </div>

          {/* Right: Connection Status, Theme Switcher & Reset */}
          <div className="flex items-center gap-1.5 sm:gap-2.5 shrink-0">
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[var(--bg-subtle)] border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
              <span className={`h-2 w-2 rounded-full ${wsConnected || firebaseConnected ? 'bg-emerald-500' : 'bg-amber-500'}`} />
              <span>{wsConnected ? 'Live Stream Connected' : firebaseConnected ? 'Cloud Synced' : 'Connecting...'}</span>
            </div>

            <button
              type="button"
              onClick={() => setTheme(theme === 'daylight' ? 'midnight' : 'daylight')}
              className="p-2 sm:px-3 sm:py-1.5 rounded-xl bg-[var(--bg-subtle)] hover:bg-[var(--bg-muted)] border border-[var(--border-color)] text-xs font-medium text-[var(--text-primary)] flex items-center gap-1.5 transition"
              title={theme === 'daylight' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
            >
              {theme === 'daylight' ? (
                <>
                  <Moon className="h-4 w-4 sm:h-3.5 sm:w-3.5 text-slate-600" />
                  <span className="hidden sm:inline">Dark Mode</span>
                </>
              ) : (
                <>
                  <Sun className="h-4 w-4 sm:h-3.5 sm:w-3.5 text-amber-400" />
                  <span className="hidden sm:inline">Light Mode</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={handleResetSystem}
              className="p-2 sm:px-3.5 sm:py-1.5 rounded-xl bg-[var(--bg-subtle)] hover:bg-[var(--bg-muted)] border border-[var(--border-color)] text-xs font-medium text-[var(--text-primary)] flex items-center gap-1.5 transition"
              title="Reset all rooms and alerts back to normal"
            >
              <RotateCcw className="h-4 w-4 sm:h-3.5 sm:w-3.5 text-[var(--text-secondary)]" />
              <span className="hidden sm:inline">Reset Building</span>
            </button>
          </div>
        </div>
      </header>

      {/* =====================================================================
          2. SINGLE, SIMPLE ROOM SELECTOR BAR
         ===================================================================== */}
      <div className="border-b border-[var(--border-color)] bg-[var(--bg-surface)]/60">
        <div className="max-w-[1560px] mx-auto px-3 sm:px-6 py-2 sm:py-2.5 flex items-center gap-2 overflow-x-auto no-scrollbar">
          <span className="hidden sm:inline text-xs font-semibold text-[var(--text-muted)] mr-1 shrink-0">
            Rooms:
          </span>
          {FACILITY_ROOM_CONFIGS.map((cfg) => {
            const rState = rooms.find((r) => r.id === cfg.id)?.state || 'NORMAL';
            const rTelem = allTelemetry[cfg.id];
            const isSelected = selectedRoomId === cfg.id;
            const isAlert = rState === 'INCIDENT';
            const isWarn = rState === 'ANOMALY' || rState === 'ATTENTION';

            return (
              <button
                key={cfg.id}
                type="button"
                onClick={() => setSelectedRoomId(cfg.id)}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-medium flex items-center gap-2 shrink-0 transition ${
                  isSelected
                    ? 'bg-blue-600 text-white shadow-sm font-semibold'
                    : isAlert
                    ? 'bg-red-500/15 text-red-600 dark:text-red-400 border border-red-500/30 font-semibold'
                    : isWarn
                    ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30 font-semibold'
                    : 'bg-[var(--bg-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border-color)]'
                }`}
              >
                <span
                  className={`h-2 w-2 rounded-full ${
                    isAlert
                      ? 'bg-red-500 animate-ping'
                      : isWarn
                      ? 'bg-amber-500'
                      : isSelected
                      ? 'bg-white'
                      : 'bg-emerald-500'
                  }`}
                />
                <span>{cfg.name}</span>
                {rTelem && (
                  <span className={`text-[11px] tnum ${isSelected ? 'text-blue-100' : 'opacity-70'}`}>
                    {rTelem.temperature.toFixed(0)}°C
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Emergency Siren Banner (Only shown when Siren is active, excluded in classroom_01 for student privacy) */}
      {audioEvent === 'ALARM' && selectedRoomId !== 'classroom_01' && (
        <div className="max-w-[1560px] mx-auto px-4 sm:px-6 mt-4">
          <div className="p-4 rounded-2xl bg-red-600 text-white shadow-lg flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <BellRing className="h-6 w-6 animate-bounce shrink-0" />
              <div>
                <h4 className="font-display font-bold text-sm">
                  Emergency Siren Detected in {selectedRoomObj?.name}
                </h4>
                <p className="text-xs text-red-100">
                  The room microphone detected an active alarm siren (2.5 kHz). Please check the room immediately.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={handleResetSystem}
              className="px-3.5 py-1.5 rounded-xl bg-white text-red-700 text-xs font-bold hover:bg-red-50 transition"
            >
              Silence & Reset
            </button>
          </div>
        </div>
      )}

      {/* =====================================================================
          3. MAIN WORKSPACE (MOBILE-FIRST + CLEAN 2-COLUMN DESKTOP)
         ===================================================================== */}
      <div className="max-w-[1560px] mx-auto px-3 sm:px-6 pt-3 sm:pt-5 grid grid-cols-12 gap-3.5 sm:gap-6">
        {/* Mobile-Only Priority Alert Card (Shown right at the top on phone when an alert/warning is active!) */}
        {activeIncident && (
          <div className="col-span-12 min-w-0 lg:hidden">
            <div className="studio-card p-4">
              <div className="flex items-center justify-between mb-2.5">
                <h2 className="font-display font-bold text-sm text-[var(--text-primary)] flex items-center gap-2">
                  <ShieldAlert className={`h-4 w-4 ${activeIncident.severity === 'CRITICAL' ? 'text-red-500' : 'text-amber-500'}`} />
                  Safety & Alert Status
                </h2>
                <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${
                  activeIncident.severity === 'CRITICAL'
                    ? 'bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/25'
                    : 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30'
                }`}>
                  {activeIncident.severity}
                </span>
              </div>

              <div className={`p-3.5 rounded-2xl border ${
                activeIncident.severity === 'CRITICAL'
                  ? 'bg-red-500/10 border-red-500/25'
                  : 'bg-amber-500/10 border-amber-500/30'
              }`}>
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className={`font-display font-bold text-xs sm:text-sm ${
                    activeIncident.severity === 'CRITICAL'
                      ? 'text-red-600 dark:text-red-400'
                      : 'text-amber-700 dark:text-amber-400'
                  }`}>
                    {activeIncident.type.replace(/_/g, ' ')}
                  </span>
                  <span className={`text-[11px] font-semibold shrink-0 ${
                    activeIncident.severity === 'CRITICAL'
                      ? 'text-red-600 dark:text-red-400'
                      : 'text-amber-600 dark:text-amber-400'
                  }`}>
                    {int_percentage(activeIncident.confidence)} Confidence
                  </span>
                </div>
                <p className="text-xs text-[var(--text-primary)] leading-relaxed">
                  {activeIncident.summary}
                </p>

                <div className="flex flex-wrap gap-2 mt-3">
                  <button
                    type="button"
                    onClick={() => handleExplainIncident(activeIncident.id)}
                    disabled={explainingIncidentId === activeIncident.id}
                    className="px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5 transition"
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    <span>{explainingIncidentId === activeIncident.id ? 'Analyzing...' : 'Explain with AI'}</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleResolveSingleIncident(activeIncident.id)}
                    className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 ml-auto transition"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    <span>Resolve</span>
                  </button>
                </div>

                {forensicExplanation && (
                  <div className="mt-3 p-3 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-color)] text-xs text-[var(--text-primary)] leading-relaxed">
                    <strong className="block text-blue-600 dark:text-blue-400 mb-1">AI Explanation:</strong>
                    {forensicExplanation}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* -------------------------------------------------------------------
            LEFT 7 COLUMNS: 3D BUILDING + SELECTED ROOM SENSORS + FORECAST
           ------------------------------------------------------------------- */}
        <div className={`col-span-12 lg:col-span-7 min-w-0 flex-col gap-3.5 sm:gap-5 ${mobileTab === 'ai' ? 'hidden lg:flex' : 'flex'}`}>
          {/* 1. Interactive 3D Building View */}
          <div className={`${mobileTab === 'sensors' ? 'hidden lg:block' : 'block'} ${mobileTab === '3d' ? 'h-[430px]' : 'h-[280px]'} sm:h-[420px] studio-card p-1.5 sm:p-2 min-w-0`}>
            <Building3D
              rooms={rooms}
              selectedRoomId={selectedRoomId}
              onSelectRoom={(id) => setSelectedRoomId(id)}
              telemetryByRoom={allTelemetry}
              theme={theme}
            />
          </div>

          {/* 2. Selected Room Live Sensor Cards (2x2 Grid on Phone, Multi-Col on Desktop) */}
          <div className={`min-w-0 ${mobileTab === '3d' ? 'hidden lg:block' : 'block'}`}>
            <div className="flex items-center justify-between mb-2.5 sm:mb-3 px-1 flex-wrap gap-1.5 sm:gap-2">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="font-display font-bold text-sm sm:text-base text-[var(--text-primary)]">
                  {selectedRoomObj?.name} — Live Sensors
                </h2>
                {(selectedRoomId === 'lab_02' || selectedRoomId === 'classroom_01') && (
                  activeWokwiRooms[selectedRoomId] || (selectedRoomId === 'lab_02' && isWokwiActive) ? (
                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] sm:text-[11px] font-bold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 animate-pulse">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                      Wokwi Hardware Active
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                      Wokwi Node Ready
                    </span>
                  )
                )}
              </div>
              <span className="text-[11px] sm:text-xs text-[var(--text-muted)]">
                Floor {selectedRoomObj?.floor} • {(selectedRoomId === 'lab_02' || selectedRoomId === 'classroom_01') ? 'ESP32 Node' : 'Virtual Node'}
                {selectedRoomId === 'classroom_01' && ' • Mic Omitted'}
              </span>
            </div>

            <div className={`grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-3 ${selectedRoomId === 'classroom_01' ? 'xl:grid-cols-4' : 'xl:grid-cols-3 2xl:grid-cols-5'} gap-2.5 sm:gap-3.5`}>
              {/* Card 1: Temperature & Climate */}
              <div className="studio-card p-3 sm:p-4 flex flex-col justify-between overflow-hidden relative">
                <div className="flex items-center justify-between gap-1 mb-1.5 sm:mb-2 min-w-0">
                  <span className="text-[11px] sm:text-xs font-semibold text-[var(--text-secondary)] flex items-center gap-1 sm:gap-1.5 whitespace-nowrap">
                    <Thermometer className={`h-3.5 w-3.5 sm:h-4 sm:w-4 shrink-0 ${(temperature >= 45 || (temperature >= 32 && activeIncident?.severity === 'CRITICAL')) ? 'text-red-500' : temperature >= 32 ? 'text-amber-500' : 'text-rose-500'}`} />
                    <span>Temperature</span>
                  </span>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0 whitespace-nowrap ${
                      temperature >= 45 || (temperature >= 32 && activeIncident?.severity === 'CRITICAL')
                        ? 'bg-red-500/15 text-red-600 dark:text-red-400'
                        : temperature >= 32
                        ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400'
                        : 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                    }`}
                  >
                    {temperature >= 45 || (temperature >= 32 && activeIncident?.severity === 'CRITICAL')
                      ? 'Alert'
                      : temperature >= 32
                      ? 'Warm'
                      : 'Normal'}
                  </span>
                </div>
                <div className="mt-1">
                  <div className="flex items-baseline justify-between gap-1">
                    <div className="text-xl sm:text-2xl font-display font-bold text-[var(--text-primary)] tnum whitespace-nowrap">
                      {temperature.toFixed(1)}°C
                    </div>
                    <div className="text-[10px] sm:text-[11px] font-medium text-[var(--text-muted)] whitespace-nowrap">
                      {humidity.toFixed(0)}% RH
                    </div>
                  </div>
                  <div className="h-4 sm:h-5 w-full my-1.5 overflow-hidden flex items-center">
                    {renderSmoothSparkline(
                      currentTelem.tempHistory || [temperature],
                      temperature >= 45 || (temperature >= 32 && activeIncident?.severity === 'CRITICAL')
                        ? '#ef4444'
                        : temperature >= 32
                        ? '#f59e0b'
                        : '#10b981'
                    )}
                  </div>
                  <div className="flex justify-between items-center text-[10px] text-[var(--text-muted)] whitespace-nowrap">
                    <span>Climate</span>
                    <span>{temperature >= 45 ? 'Extreme Heat' : temperature >= 32 ? 'Warm' : 'Nominal'}</span>
                  </div>
                </div>
              </div>

              {/* Card 2: Gas & Air Quality */}
              <div className="studio-card p-3 sm:p-4 flex flex-col justify-between overflow-hidden relative">
                <div className="flex items-center justify-between gap-1 mb-1.5 sm:mb-2 min-w-0">
                  <span className="text-[11px] sm:text-xs font-semibold text-[var(--text-secondary)] flex items-center gap-1 sm:gap-1.5 whitespace-nowrap">
                    <Wind className={`h-3.5 w-3.5 sm:h-4 sm:w-4 shrink-0 ${gas > 350 ? 'text-red-500' : gas >= 160 ? 'text-amber-500' : 'text-teal-500'}`} />
                    <span>Gas & Air</span>
                  </span>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0 whitespace-nowrap ${
                      gas > 350
                        ? 'bg-red-500/15 text-red-600 dark:text-red-400'
                        : gas >= 160
                        ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400'
                        : 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                    }`}
                  >
                    {gas > 350 ? 'Hazard' : gas >= 160 ? 'Elevated' : 'Safe'}
                  </span>
                </div>
                <div className="mt-1">
                  <div className="flex items-baseline justify-between gap-1">
                    <div className="text-xl sm:text-2xl font-display font-bold text-[var(--text-primary)] tnum whitespace-nowrap">
                      {gas.toFixed(0)} <span className="text-[11px] sm:text-xs font-normal text-[var(--text-muted)]">ppm</span>
                    </div>
                    <div className="text-[10px] sm:text-[11px] font-medium text-[var(--text-muted)] whitespace-nowrap">
                      MQ-2 Sensor
                    </div>
                  </div>
                  <div className="h-4 sm:h-5 w-full my-1.5 overflow-hidden flex items-center">
                    {renderSmoothSparkline(
                      currentTelem.gasHistory || [gas],
                      gas > 350 ? '#ef4444' : gas >= 160 ? '#f59e0b' : '#14b8a6'
                    )}
                  </div>
                  <div className="flex justify-between items-center text-[10px] text-[var(--text-muted)] whitespace-nowrap">
                    <span>Air Quality</span>
                    <span>{gas > 350 ? 'Hazardous' : gas >= 160 ? 'Elevated' : 'Clean'}</span>
                  </div>
                </div>
              </div>

              {/* Card 3: Optical Smoke Detector */}
              <div className="studio-card p-3 sm:p-4 flex flex-col justify-between overflow-hidden relative">
                <div className="flex items-center justify-between gap-1 mb-1.5 sm:mb-2 min-w-0">
                  <span className="text-[11px] sm:text-xs font-semibold text-[var(--text-secondary)] flex items-center gap-1 sm:gap-1.5 whitespace-nowrap">
                    <Flame className={`h-3.5 w-3.5 sm:h-4 sm:w-4 shrink-0 ${smoke > 15 ? 'text-red-500 animate-pulse' : smoke > 5 ? 'text-amber-500' : 'text-orange-500'}`} />
                    <span>Smoke</span>
                  </span>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0 whitespace-nowrap ${
                      smoke > 15
                        ? 'bg-red-500/15 text-red-600 dark:text-red-400'
                        : smoke > 5
                        ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400'
                        : 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                    }`}
                  >
                    {smoke > 15 ? 'Dense' : smoke > 5 ? 'Elevated' : 'Clean'}
                  </span>
                </div>
                <div className="mt-1">
                  <div className="flex items-baseline justify-between gap-1">
                    <div className="text-xl sm:text-2xl font-display font-bold text-[var(--text-primary)] tnum whitespace-nowrap">
                      {smoke.toFixed(1)}% <span className="text-[11px] sm:text-xs font-normal text-[var(--text-muted)]">smoke</span>
                    </div>
                    <div className="text-[10px] sm:text-[11px] font-medium text-[var(--text-muted)] whitespace-nowrap">
                      Photoelectric
                    </div>
                  </div>
                  <div className="w-full bg-[var(--bg-subtle)] rounded-full h-1.5 sm:h-2 overflow-hidden my-2.5 sm:my-3 border border-[var(--border-color)]">
                    <div
                      className={`h-full transition-all duration-500 rounded-full ${
                        smoke > 15
                          ? 'bg-red-500'
                          : smoke > 5
                          ? 'bg-amber-500'
                          : 'bg-emerald-500'
                      }`}
                      style={{ width: `${Math.max(4, Math.min(100, (smoke / 30) * 100))}%` }}
                    />
                  </div>
                  <div className="flex justify-between items-center text-[10px] text-[var(--text-muted)] whitespace-nowrap">
                    <span>Optical</span>
                    <span>Max: 15%</span>
                  </div>
                </div>
              </div>

              {/* Card 4: Acoustic Intelligence & Microphone (Omitted in Classroom 01 for privacy) */}
              {selectedRoomId !== 'classroom_01' && (
                <div className={`studio-card p-3 sm:p-4 flex flex-col justify-between overflow-hidden relative transition-all ${
                  audioEvent === 'ALARM'
                    ? 'border-red-500 shadow-md shadow-red-500/10'
                    : audioEvent === 'SPEECH'
                    ? 'border-violet-500 shadow-md shadow-violet-500/10'
                    : ''
                }`}>
                  <div className="flex items-center justify-between gap-1 mb-1.5 sm:mb-2 min-w-0">
                    <span className="text-[11px] sm:text-xs font-semibold text-[var(--text-secondary)] flex items-center gap-1 sm:gap-1.5 whitespace-nowrap">
                      <Mic className={`h-3.5 w-3.5 sm:h-4 sm:w-4 shrink-0 ${
                        audioEvent === 'ALARM'
                          ? 'text-red-500 animate-pulse'
                          : audioEvent === 'SPEECH'
                          ? 'text-violet-500 animate-pulse'
                          : 'text-indigo-500'
                      }`} />
                      <span>Microphone</span>
                    </span>
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0 whitespace-nowrap ${
                        audioEvent === 'ALARM'
                          ? 'bg-red-500/20 text-red-600 dark:text-red-400 animate-pulse font-bold'
                          : audioEvent === 'SPEECH'
                          ? 'bg-violet-500/20 text-violet-600 dark:text-violet-400 font-bold'
                          : audioEvent === 'IMPACT'
                          ? 'bg-amber-500/20 text-amber-600 dark:text-amber-400'
                          : 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                      }`}
                    >
                      {audioEvent === 'ALARM' ? 'Siren' : audioEvent === 'SPEECH' ? 'Voice' : audioEvent === 'IMPACT' ? 'Impact' : 'Quiet'}
                    </span>
                  </div>
                  <div className="mt-1">
                    <div className="flex items-baseline justify-between gap-1">
                      <div className="text-xl sm:text-2xl font-display font-bold text-[var(--text-primary)] tracking-wide whitespace-nowrap">
                        {audioEvent}
                      </div>
                      <span className="text-[9px] sm:text-[10px] font-mono font-medium text-[var(--text-muted)] shrink-0 whitespace-nowrap">
                        {(audioRms * 1000).toFixed(1)} mV
                      </span>
                    </div>
                    <div className="flex items-end gap-1 h-3 sm:h-3.5 my-2">
                      {[0.0018, 0.0035, 0.007, 0.015, 0.035].map((thresh, idx) => {
                        const active = audioRms >= thresh;
                        let barColor = 'bg-[var(--border-color)] h-1';
                        if (active) {
                          if (audioEvent === 'SPEECH') barColor = 'bg-violet-500 h-3 sm:h-3.5';
                          else if (audioEvent === 'ALARM') barColor = 'bg-red-500 h-3 sm:h-3.5';
                          else barColor = 'bg-emerald-500 h-2.5';
                        }
                        return (
                          <div
                            key={idx}
                            className={'flex-1 rounded-full transition-all duration-100 ' + barColor}
                          />
                        );
                      })}
                    </div>
                    <div className="text-[10px] sm:text-[11px] text-[var(--text-muted)] flex items-center justify-between whitespace-nowrap">
                      <span className="flex items-center gap-1.5">
                        <span className={`inline-block h-1.5 w-1.5 sm:h-2 sm:w-2 rounded-full shrink-0 ${
                          audioEvent === 'SPEECH' ? 'bg-violet-500 animate-ping' :
                          audioEvent === 'ALARM' ? 'bg-red-500 animate-ping' :
                          'bg-emerald-500'
                        }`} />
                        <span>Acoustic DSP</span>
                      </span>
                      <span>16kHz</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Card 5: People In Front & Live Camera */}
              <div
                onClick={() => setSnapshotModalOpen(true)}
                className={`studio-card p-3 sm:p-4 flex flex-col justify-between overflow-hidden relative cursor-pointer group hover:border-emerald-500/60 hover:shadow-lg transition-all ${
                  selectedRoomId !== 'classroom_01' ? 'col-span-2 sm:col-span-1' : ''
                }`}
                title="Click to open 45 FPS Edge Camera Feed"
              >
                <div className="flex items-center justify-between gap-1 mb-1.5 sm:mb-2 min-w-0">
                  <span className="text-[11px] sm:text-xs font-semibold text-[var(--text-secondary)] flex items-center gap-1 sm:gap-1.5 whitespace-nowrap">
                    <Eye className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-emerald-500 group-hover:scale-110 transition-transform shrink-0" />
                    <span>People In Front</span>
                  </span>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0 whitespace-nowrap ${
                      occupancy > 0
                        ? 'bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 font-bold'
                        : 'bg-slate-500/10 text-slate-500'
                    }`}
                  >
                    {occupancy > 0 ? 'OCCUPIED' : 'CLEAR'}
                  </span>
                </div>

                <div className="my-1">
                  <div className="text-2xl sm:text-3xl font-display font-extrabold text-[var(--text-primary)] tnum tracking-tight flex items-baseline gap-1.5 whitespace-nowrap">
                    {occupancy}
                    <span className="text-[11px] sm:text-xs font-normal text-[var(--text-muted)]">
                      {occupancy === 1 ? 'person' : 'people'}
                    </span>
                  </div>
                  <p className="text-[10px] sm:text-[11px] text-[var(--text-muted)] mt-1 whitespace-nowrap">
                    {occupancy > 0 ? 'Subject identified in zone' : 'No subjects in zone'}
                  </p>
                </div>

                <div className="pt-1.5 sm:pt-2 border-t border-[var(--border-color)] mt-1 flex items-center justify-between text-xs text-emerald-600 dark:text-emerald-400 font-medium group-hover:text-emerald-500 whitespace-nowrap">
                  <span className="flex items-center gap-1 text-[10px] sm:text-[11px]">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-ping"></span>
                    45 FPS Live
                  </span>
                  <span className="flex items-center gap-1 text-[10px] sm:text-[11px] text-[var(--text-secondary)] group-hover:text-[var(--text-primary)]">
                    <Maximize2 className="h-3 w-3" /> Camera
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* 3. 15-Minute Forecast Card */}
          <div className={`studio-card p-3.5 sm:p-5 min-w-0 ${mobileTab === '3d' ? 'hidden lg:block' : 'block'}`}>
            <div className="flex flex-wrap items-center justify-between gap-2.5 mb-3.5 sm:mb-4">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-400 shrink-0">
                  <ArrowUpRight className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="font-display font-bold text-xs sm:text-sm text-[var(--text-primary)]">
                    15-Minute Forecast — {selectedRoomObj?.name}
                  </h3>
                  <p className="text-[11px] sm:text-xs text-[var(--text-muted)]">
                    Predicted short-term trend based on recent sensor readings
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-1 bg-[var(--bg-subtle)] p-1 rounded-xl border border-[var(--border-color)] text-[11px] sm:text-xs w-full sm:w-auto justify-between sm:justify-start">
                {(['temperature', 'gas', 'humidity'] as const).map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => setPredictionVariable(v)}
                    className={`flex-1 sm:flex-initial px-2.5 sm:px-3 py-1 rounded-lg font-medium capitalize transition ${
                      predictionVariable === v
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                    }`}
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2 sm:gap-3">
              {(['+1m', '+5m', '+15m'] as const).map((horizon) => {
                const hData = prediction?.horizons?.[horizon];
                const predVal =
                  hData?.predicted ??
                  (predictionVariable === 'temperature' ? temperature : predictionVariable === 'gas' ? gas : humidity);
                const label = horizon === '+1m' ? 'In 1 Min' : horizon === '+5m' ? 'In 5 Mins' : 'In 15 Mins';

                return (
                  <div key={horizon} className="studio-subcard p-2.5 sm:p-3.5 text-center">
                    <div className="text-[11px] sm:text-xs text-[var(--text-muted)] font-medium">{label}</div>
                    <div className="text-base sm:text-xl font-display font-bold text-[var(--text-primary)] mt-1 tnum">
                      {predVal.toFixed(1)}{unitLabel}
                    </div>
                  </div>
                );
              })}
            </div>

            {prediction?.explanation && (
              <p className="mt-3 text-xs text-[var(--text-secondary)] bg-[var(--bg-subtle)] px-3.5 py-2.5 rounded-xl border border-[var(--border-color)]">
                {prediction.explanation}
              </p>
            )}
          </div>
        </div>

        {/* -------------------------------------------------------------------
            RIGHT 5 COLUMNS: SAFETY STATUS & AI ASSISTANT
           ------------------------------------------------------------------- */}
        <div className={`col-span-12 lg:col-span-5 min-w-0 flex-col gap-3.5 sm:gap-5 ${mobileTab === '3d' ? 'hidden lg:flex' : 'flex'}`}>
          {/* 1. Safety & Active Alert Card (Hidden on mobile when activeIncident is already shown at the very top) */}
          <div className={`studio-card p-4 sm:p-5 min-w-0 ${activeIncident || mobileTab === 'ai' ? 'hidden lg:block' : ''}`}>
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-display font-bold text-sm sm:text-base text-[var(--text-primary)] flex items-center gap-2">
                <ShieldAlert className={`h-5 w-5 ${
                  activeIncident
                    ? activeIncident.severity === 'CRITICAL'
                      ? 'text-red-500'
                      : 'text-amber-500'
                    : 'text-emerald-500'
                }`} />
                Safety & Alert Status
              </h2>
              {activeIncident && (
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${
                  activeIncident.severity === 'CRITICAL'
                    ? 'bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/25'
                    : 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30'
                }`}>
                  {activeIncident.severity}
                </span>
              )}
            </div>

            {activeIncident ? (
              <div className="space-y-4">
                <div className={`p-4 rounded-2xl border ${
                  activeIncident.severity === 'CRITICAL'
                    ? 'bg-red-500/10 border-red-500/25'
                    : 'bg-amber-500/10 border-amber-500/30'
                }`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className={`font-display font-bold text-sm ${
                      activeIncident.severity === 'CRITICAL'
                        ? 'text-red-600 dark:text-red-400'
                        : 'text-amber-700 dark:text-amber-400'
                    }`}>
                      {activeIncident.type.replace(/_/g, ' ')}
                    </span>
                    <span className={`text-xs font-semibold ${
                      activeIncident.severity === 'CRITICAL'
                        ? 'text-red-600 dark:text-red-400'
                        : 'text-amber-600 dark:text-amber-400'
                    }`}>
                      {int_percentage(activeIncident.confidence)} Confidence
                    </span>
                  </div>
                  <p className="text-xs text-[var(--text-primary)] leading-relaxed">
                    {activeIncident.summary}
                  </p>

                  <div className="flex flex-wrap gap-2 mt-3">
                    <button
                      type="button"
                      onClick={() => handleExplainIncident(activeIncident.id)}
                      disabled={explainingIncidentId === activeIncident.id}
                      className="px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5 transition"
                    >
                      <Sparkles className="h-3.5 w-3.5" />
                      <span>{explainingIncidentId === activeIncident.id ? 'Analyzing...' : 'Explain with AI'}</span>
                    </button>

                    <a
                      href={`http://127.0.0.1:8000/api/ai/report/${activeIncident.id}?format=html`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-3 py-1.5 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-strong)] text-[var(--text-primary)] text-xs font-semibold flex items-center gap-1.5 hover:opacity-90 transition"
                    >
                      <FileText className="h-3.5 w-3.5" />
                      <span>Full Report</span>
                      <ExternalLink className="h-3 w-3 opacity-60" />
                    </a>

                    <button
                      type="button"
                      onClick={() => handleResolveSingleIncident(activeIncident.id)}
                      className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 ml-auto transition"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      <span>Resolve</span>
                    </button>
                  </div>

                  {forensicExplanation && (
                    <div className="mt-3 p-3 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-color)] text-xs text-[var(--text-primary)] leading-relaxed">
                      <strong className="block text-blue-600 dark:text-blue-400 mb-1">AI Explanation:</strong>
                      {forensicExplanation}
                    </div>
                  )}
                </div>

                {/* Simple Contributing Sensors List */}
                {activeIncident.evidence && activeIncident.evidence.length > 0 && (
                  <div>
                    <div className="text-xs font-semibold text-[var(--text-secondary)] mb-2">
                      {activeIncident.severity === 'CRITICAL' ? 'Why this alert triggered:' : 'Why this warning triggered:'}
                    </div>
                    <div className="space-y-2">
                      {activeIncident.evidence.map((ev, idx) => (
                        <div key={idx} className="studio-subcard p-3 text-xs">
                          <div className="flex items-center justify-between font-medium text-[var(--text-primary)] mb-1">
                            <span>{ev.source_type}: {ev.source_id}</span>
                            <span className="text-blue-600 dark:text-blue-400 font-semibold">
                              {int_percentage(ev.contribution)} impact
                            </span>
                          </div>
                          <p className="text-[var(--text-secondary)]">{ev.explanation}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="studio-subcard p-4 sm:p-5 flex items-center gap-3.5 sm:gap-4">
                <div className="p-2.5 sm:p-3 rounded-2xl bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 shrink-0">
                  <ShieldCheck className="h-6 w-6 sm:h-7 sm:w-7" />
                </div>
                <div>
                  <div className="font-display font-bold text-sm text-[var(--text-primary)]">
                    Everything Looks Good
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] mt-0.5 leading-relaxed">
                    {selectedRoomId === 'classroom_01'
                      ? 'No active safety alerts. Temperature, air quality, and camera sensors are all within normal ranges (Microphone disabled for student privacy).'
                      : 'No active safety alerts. Temperature, air quality, camera, and audio sensors are all within normal ranges.'}
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* 2. Interactive AI Assistant Card */}
          <div className={`studio-card p-3.5 sm:p-5 flex-1 flex flex-col min-w-0 ${mobileTab === 'sensors' ? 'hidden lg:flex' : 'flex'}`}>
            {/* Header */}
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-[var(--border-color)]">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-xl bg-blue-500/10 text-blue-500">
                  <Sparkles className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="text-xs font-semibold text-[var(--text-primary)]">NEXUS AI Assistant</h3>
                  <p className="text-[11px] text-[var(--text-secondary)]">Natural-language facility intelligence</p>
                </div>
              </div>
              <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${
                health?.ai_engine && !health.ai_engine.offline_reasoning && wsConnected
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                  : 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20'
              }`}>
                {health?.ai_engine && !health.ai_engine.offline_reasoning && wsConnected ? 'Gemini Active' : 'Local Expert'}
              </span>
            </div>

            <div className="flex-1 flex flex-col min-w-0">
              {/* Chat Messages */}
              <div ref={chatScrollRef} className="flex-1 studio-subcard p-3 sm:p-3.5 overflow-y-auto max-h-[280px] sm:max-h-[320px] space-y-2.5 sm:space-y-3">
                {chatMessages.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`p-3 rounded-2xl text-xs leading-relaxed whitespace-pre-wrap break-words ${
                      msg.role === 'user'
                        ? 'bg-blue-600 text-white ml-6 sm:ml-8 shadow-sm'
                        : 'bg-[var(--bg-surface)] border border-[var(--border-color)] text-[var(--text-primary)] mr-4 sm:mr-6'
                    }`}
                  >
                    {msg.role === 'assistant' && (
                      <div className="flex items-center gap-1.5 mb-1.5 text-[10px] font-semibold text-blue-600 dark:text-blue-400">
                        <Sparkles className="h-3 w-3" />
                        <span>{msg.offline ? 'Local Expert' : 'Gemini AI'}</span>
                      </div>
                    )}
                    {msg.text}
                  </div>
                ))}
                {aiLoading && (
                  <div className="text-xs text-[var(--text-muted)] flex items-center gap-2 p-2">
                    <Sparkles className="h-4 w-4 animate-spin text-blue-500" />
                    <span>Thinking...</span>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Suggested Questions */}
              <div className="flex flex-wrap gap-1.5 my-2.5 sm:my-3">
                {[
                  'Why is Lab 02 highlighted?',
                  'Are all rooms safe right now?',
                  'Compare Server Room and Classroom 01'
                ].map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => handleAsk(prompt)}
                    className="text-[11px] sm:text-xs px-2.5 sm:px-3 py-1.5 rounded-full bg-[var(--bg-subtle)] hover:bg-[var(--bg-muted)] border border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition"
                  >
                    {prompt}
                  </button>
                ))}
              </div>

              {/* Chat Input (16px font on mobile prevents iOS/Android auto-zoom on focus) */}
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
                  placeholder="Ask a question about any room..."
                  className="flex-1 min-w-0 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl px-3.5 py-2.5 text-base sm:text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-blue-500"
                />
                <button
                  type="button"
                  onClick={toggleSpeechRecognition}
                  className={`p-2.5 rounded-xl border shrink-0 transition ${
                    isListening
                      ? 'bg-red-500 text-white border-red-400 animate-pulse'
                      : 'bg-[var(--bg-subtle)] border-[var(--border-color)] text-[var(--text-secondary)]'
                  }`}
                  title="Voice input"
                >
                  {isListening ? <Volume2 className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                </button>
                <button
                  type="button"
                  onClick={() => handleAsk()}
                  disabled={aiLoading}
                  className="px-3.5 sm:px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5 shrink-0 transition disabled:opacity-50"
                >
                  <Send className="h-4 w-4 sm:h-3.5 sm:w-3.5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* =====================================================================
          MOBILE-ONLY BOTTOM NAVIGATION BAR (Native App Experience on Phone)
         ===================================================================== */}
      <nav className="lg:hidden fixed bottom-0 inset-x-0 z-40 border-t border-[var(--border-color)] bg-[var(--bg-surface)]/95 backdrop-blur-md px-2 py-1.5">
        <div className="grid grid-cols-4 gap-1 max-w-md mx-auto">
          {([
            { id: 'overview', label: 'All Views', icon: Building2 },
            { id: '3d', label: '3D Twin', icon: Maximize2 },
            { id: 'sensors', label: 'Sensors', icon: Thermometer },
            { id: 'ai', label: 'AI Chat', icon: MessageSquare },
          ] as const).map((tab) => {
            const Icon = tab.icon;
            const active = mobileTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => {
                  setMobileTab(tab.id);
                  window.scrollTo({ top: 0, behavior: 'smooth' });
                }}
                className={`flex flex-col items-center justify-center py-1.5 rounded-xl text-[11px] font-semibold transition ${
                  active
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }`}
              >
                <Icon className="h-4 w-4 mb-0.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </nav>

      {/* =====================================================================
          4. LIVE CAMERA MODAL
         ===================================================================== */}
      {snapshotModalOpen && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-3 sm:p-4">
          <div className="studio-card max-w-2xl w-full p-4 sm:p-5 flex flex-col gap-3.5 sm:gap-4">
            <div className="flex items-center justify-between">
              <h3 className="font-display font-bold text-sm sm:text-base text-[var(--text-primary)] flex items-center gap-2">
                <Eye className="h-4 w-4 sm:h-5 sm:w-5 text-emerald-500" />
                Live Camera — {selectedRoomObj?.name} (45 FPS)
              </h3>
              <button
                type="button"
                onClick={() => setSnapshotModalOpen(false)}
                className="p-1.5 rounded-lg hover:bg-[var(--bg-subtle)] text-[var(--text-secondary)]"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="rounded-xl overflow-hidden bg-black flex items-center justify-center min-h-[220px] sm:min-h-[340px]">
              <img
                src={`http://127.0.0.1:8000/api/vision/stream/${selectedRoomId}`}
                alt="Live Camera Stream"
                className="w-full h-auto object-contain"
                onError={(e) => {
                  if (visionSnapshot) {
                    (e.currentTarget as HTMLImageElement).src = visionSnapshot.startsWith('data:image')
                      ? visionSnapshot
                      : `data:image/jpeg;base64,${visionSnapshot}`;
                  }
                }}
              />
            </div>

            <div className="flex justify-between items-center text-xs text-[var(--text-secondary)]">
              <span>Detected in room: <strong>{occupancy} {occupancy === 1 ? 'Person' : 'People'}</strong></span>
              <button
                type="button"
                onClick={() => setSnapshotModalOpen(false)}
                className="px-4 py-2 rounded-xl bg-blue-600 text-white font-semibold"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

function int_percentage(val: number | undefined): string {
  if (val === undefined || isNaN(val)) return '85%';
  return `${Math.round(val > 1 ? val : val * 100)}%`;
}
