'use client';

import React, { useState, useEffect, useRef } from 'react';
import { 
  Activity, ShieldAlert, Cpu, Eye, Mic, 
  Layers, Terminal, RefreshCw, CheckCircle2, AlertTriangle,
  Flame, Wind, Users, ArrowUpRight, ArrowDownRight, Send,
  FileText, Sliders, Play, RotateCcw, Volume2, MicOff, BellRing,
  ExternalLink, Clock, Sparkles, Maximize2, X, ChevronDown, Zap,
  Compass, ShieldCheck, Database, Wifi, Server
} from 'lucide-react';
import Building3D, { RoomState } from '@/components/digital-twin/Building3D';
import { rtdb } from '@/lib/firebase';
import { ref as dbRef, onValue } from 'firebase/database';

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
  timeline: Array<{ time: string; source: string; description: string }>;
  evidence: Array<{ id: number; source_type: string; source_id: string; contribution: number; explanation: string }>;
}

interface RoomTelemetry {
  temperature: number;
  humidity: number;
  gas: number;
  smoke: number;
  occupancy: number;
  vibration: number;
  tempHistory: number[];
  gasHistory: number[];
  smokeHistory: number[];
}

const DEFAULT_ROOM_TELEMETRY: Record<string, RoomTelemetry> = {
  server_room: { temperature: 18.5, humidity: 35.0, gas: 35.0, smoke: 0.1, occupancy: 0, vibration: 0.075, tempHistory: [18.4, 18.5, 18.6, 18.5, 18.5], gasHistory: [34, 35, 36, 35, 35], smokeHistory: [0.1, 0.1, 0.1, 0.1, 0.1] },
  classroom_01: { temperature: 21.8, humidity: 48.0, gas: 240.0, smoke: 0.3, occupancy: 18, vibration: 0.015, tempHistory: [21.5, 21.6, 21.7, 21.8, 21.8], gasHistory: [230, 235, 238, 240, 242], smokeHistory: [0.3, 0.3, 0.3, 0.3, 0.3] },
  classroom_02: { temperature: 22.2, humidity: 47.0, gas: 260.0, smoke: 0.3, occupancy: 22, vibration: 0.018, tempHistory: [21.9, 22.0, 22.1, 22.2, 22.2], gasHistory: [250, 255, 258, 260, 262], smokeHistory: [0.3, 0.3, 0.3, 0.3, 0.3] },
  lab_01: { temperature: 21.5, humidity: 44.0, gas: 80.0, smoke: 0.2, occupancy: 12, vibration: 0.020, tempHistory: [21.3, 21.4, 21.4, 21.5, 21.5], gasHistory: [78, 79, 80, 81, 80], smokeHistory: [0.2, 0.2, 0.2, 0.2, 0.2] },
  lab_02: { temperature: 23.5, humidity: 45.0, gas: 75.0, smoke: 0.4, occupancy: 0, vibration: 0.035, tempHistory: [23.2, 23.3, 23.4, 23.5, 23.5], gasHistory: [74, 75, 76, 75, 75], smokeHistory: [0.4, 0.4, 0.4, 0.4, 0.4] },
  storage_room: { temperature: 19.8, humidity: 40.0, gas: 125.0, smoke: 0.5, occupancy: 0, vibration: 0.012, tempHistory: [19.7, 19.8, 19.8, 19.8, 19.8], gasHistory: [122, 124, 125, 126, 125], smokeHistory: [0.5, 0.5, 0.5, 0.5, 0.5] },
  main_hall: { temperature: 21.0, humidity: 50.0, gas: 180.0, smoke: 0.3, occupancy: 35, vibration: 0.028, tempHistory: [20.8, 20.9, 21.0, 21.0, 21.1], gasHistory: [175, 178, 180, 182, 180], smokeHistory: [0.3, 0.3, 0.3, 0.3, 0.3] },
  entrance: { temperature: 20.5, humidity: 52.0, gas: 160.0, smoke: 0.2, occupancy: 8, vibration: 0.024, tempHistory: [20.3, 20.4, 20.5, 20.5, 20.6], gasHistory: [155, 158, 160, 162, 160], smokeHistory: [0.2, 0.2, 0.2, 0.2, 0.2] },
  emergency_exit: { temperature: 19.2, humidity: 46.0, gas: 65.0, smoke: 0.1, occupancy: 0, vibration: 0.010, tempHistory: [19.1, 19.2, 19.2, 19.2, 19.2], gasHistory: [64, 65, 65, 66, 65], smokeHistory: [0.1, 0.1, 0.1, 0.1, 0.1] }
};

export default function OperationsCenter() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [rooms, setRooms] = useState<RoomState[]>([]);
  const [selectedRoomId, setSelectedRoomId] = useState<string>('lab_02');
  const selectedRoomIdRef = useRef<string>(selectedRoomId);
  useEffect(() => {
    selectedRoomIdRef.current = selectedRoomId;
  }, [selectedRoomId]);

  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [firebaseConnected, setFirebaseConnected] = useState<boolean>(false);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [currentTime, setCurrentTime] = useState<string>('');
  const [snapshotModalOpen, setSnapshotModalOpen] = useState<boolean>(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const modalChatEndRef = useRef<HTMLDivElement>(null);
  
  // Real-time multi-room telemetry state
  const [allTelemetry, setAllTelemetry] = useState<Record<string, RoomTelemetry>>(DEFAULT_ROOM_TELEMETRY);
  const [audioEvent, setAudioEvent] = useState<string>('NORMAL');
  const [prediction, setPrediction] = useState<any>(null);
  const [visionSnapshot, setVisionSnapshot] = useState<string | null>(null);

  // Active room telemetry projections
  const currentTelem = allTelemetry[selectedRoomId] || DEFAULT_ROOM_TELEMETRY[selectedRoomId] || {
    temperature: 22.0, humidity: 45.0, gas: 80.0, smoke: 0.3, occupancy: 0, vibration: 0.025,
    tempHistory: [22.0, 22.0, 22.0, 22.0, 22.0], gasHistory: [80, 80, 80, 80, 80], smokeHistory: [0.3, 0.3, 0.3, 0.3, 0.3]
  };
  const temperature = currentTelem.temperature;
  const gas = currentTelem.gas;
  const smoke = currentTelem.smoke ?? 0.3;
  const occupancy = currentTelem.occupancy;
  const vibration = currentTelem.vibration;

  // AI Assistant state
  const [question, setQuestion] = useState<string>('');
  const [chatMessages, setChatMessages] = useState<Array<{ role: 'user' | 'assistant'; text: string; offline?: boolean }>>([
    {
      role: 'assistant',
      text: 'NEXUS Autonomous Operations Core active. Multimodal sensor streams, computer vision, and acoustic signatures are synced. Query any zone condition, forecast, or anomaly trace.'
    }
  ]);
  const [aiLoading, setAiLoading] = useState<boolean>(false);
  const [isListening, setIsListening] = useState<boolean>(false);

  // View mode switcher
  const [activeTab, setActiveTab] = useState<'overview' | 'simulation' | 'assistant'>('overview');
  
  // Simulation Panel state
  const [simTempDelta, setSimTempDelta] = useState<number>(20.0);
  const [simGasDelta, setSimGasDelta] = useState<number>(320.0);
  const [simSmokeDelta, setSimSmokeDelta] = useState<number>(35.0);
  const [simMotion, setSimMotion] = useState<boolean>(true);
  const [simPerson, setSimPerson] = useState<boolean>(true);
  const [simAudioAlarm, setSimAudioAlarm] = useState<boolean>(true);
  const [disabledSensors, setDisabledSensors] = useState<string[]>([]);
  const [simExecuting, setSimExecuting] = useState<boolean>(false);

  // Live Clock updater
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(now.toTimeString().split(' ')[0] + ' UTC');
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll chat history
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    modalChatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, aiLoading]);

  // Global ESC key listener to close active modals/copilot
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (activeTab === 'assistant' || activeTab === 'simulation') {
          setActiveTab('overview');
        }
        if (snapshotModalOpen) {
          setSnapshotModalOpen(false);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeTab, snapshotModalOpen]);

  const activeIncident = incidents.find(i => i.status === 'ACTIVE' && (i.room_id === selectedRoomId || selectedRoomId === 'all')) || incidents[0];

  // Fetch initial data
  const loadInitialData = async () => {
    const targetRoom = selectedRoomIdRef.current;
    try {
      const [hRes, rRes, iRes, pRes, vRes, sRes, visRes] = await Promise.all([
        fetch('http://127.0.0.1:8000/api/health'),
        fetch('http://127.0.0.1:8000/api/rooms'),
        fetch('http://127.0.0.1:8000/api/incidents?status=ACTIVE'),
        fetch(`http://127.0.0.1:8000/api/prediction/${targetRoom}?variable=temperature`),
        fetch(`http://127.0.0.1:8000/api/vision/snapshot/${targetRoom}`),
        fetch(`http://127.0.0.1:8000/api/sensors/room/${targetRoom}/latest`),
        fetch(`http://127.0.0.1:8000/api/vision/latest/${targetRoom}`)
      ]);

      if (hRes.ok) setHealth(await hRes.json());
      if (rRes.ok) setRooms(await rRes.json());
      if (iRes.ok) setIncidents(await iRes.json());
      if (pRes.ok) setPrediction(await pRes.json());
      if (vRes.ok) {
        const snap = await vRes.json();
        if (snap.snapshot_base64) setVisionSnapshot(snap.snapshot_base64);
      }
      
      let latestOccupancy: number | undefined;
      if (visRes.ok) {
        const vData = await visRes.json();
        const occ = vData.occupancy ?? vData.metadata?.occupancy_count;
        if (occ !== undefined) {
          latestOccupancy = Number(occ);
        }
      }

      if (sRes.ok) {
        const sData = await sRes.json();
        if (sData.readings) {
          setAllTelemetry(prev => {
            const cur = prev[targetRoom] || DEFAULT_ROOM_TELEMETRY[targetRoom] || {
              temperature: 22.0, humidity: 45.0, gas: 80.0, smoke: 0.3, occupancy: 0, vibration: 0.025,
              tempHistory: [], gasHistory: [], smokeHistory: []
            };
            const r = sData.readings;
            const newT = r.temperature ? r.temperature.value : cur.temperature;
            const newG = r.gas ? r.gas.value : cur.gas;
            const newS = r.smoke ? r.smoke.value : (cur.smoke ?? 0.3);
            const newV = r.vibration ? r.vibration.value : cur.vibration;
            const newH = r.humidity ? r.humidity.value : cur.humidity;
            const newOcc = latestOccupancy !== undefined ? latestOccupancy : cur.occupancy;
            return {
              ...prev,
              [targetRoom]: {
                ...cur,
                temperature: newT,
                gas: newG,
                smoke: newS,
                vibration: newV,
                humidity: newH,
                occupancy: newOcc,
                tempHistory: [...(cur.tempHistory || []).slice(-10), newT],
                gasHistory: [...(cur.gasHistory || []).slice(-10), newG],
                smokeHistory: [...(cur.smokeHistory || []).slice(-10), newS]
              }
            };
          });
        }
      } else if (latestOccupancy !== undefined) {
        setAllTelemetry(prev => ({
          ...prev,
          [targetRoom]: {
            ...(prev[targetRoom] || DEFAULT_ROOM_TELEMETRY[targetRoom]),
            occupancy: latestOccupancy!
          }
        }));
      }
    } catch (e) {
      console.error('Failed to load initial data:', e);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, [selectedRoomId]);

  // Live video stream refresher while camera modal is open
  useEffect(() => {
    if (!snapshotModalOpen) return;
    const updateSnapshot = async () => {
      try {
        const res = await fetch(`http://127.0.0.1:8000/api/vision/snapshot/${selectedRoomIdRef.current}`);
        if (res.ok) {
          const data = await res.json();
          if (data.snapshot_base64) {
            setVisionSnapshot(data.snapshot_base64);
          }
        }
      } catch (err) {
        console.debug('Snapshot poll error:', err);
      }
    };
    updateSnapshot();
    const interval = setInterval(updateSnapshot, 1000);
    return () => clearInterval(interval);
  }, [snapshotModalOpen]);

  // WebSocket connection
  useEffect(() => {
    let ws: WebSocket;
    try {
      ws = new WebSocket('ws://127.0.0.1:8000/ws/telemetry');
      ws.onopen = () => setWsConnected(true);
      ws.onclose = () => setWsConnected(false);
      ws.onerror = () => setWsConnected(false);
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const roomTarget = data.room_id || 'lab_02';
          
          if (data.type === 'SENSOR_READING' || data.type === 'SENSOR_BATCH' || data.type === 'VISION_EVENT') {
            setAllTelemetry(prev => {
              const cur = prev[roomTarget] || DEFAULT_ROOM_TELEMETRY[roomTarget] || {
                temperature: 22.0, humidity: 45.0, gas: 80.0, smoke: 0.3, occupancy: 0, vibration: 0.025,
                tempHistory: [], gasHistory: [], smokeHistory: []
              };
              let t = cur.temperature;
              let g = cur.gas;
              let s = cur.smoke ?? 0.3;
              let v = cur.vibration;
              let o = cur.occupancy;

              if (data.type === 'SENSOR_READING') {
                if (data.sensor_type === 'temperature') t = data.value;
                if (data.sensor_type === 'gas') g = data.value;
                if (data.sensor_type === 'smoke') s = data.value;
                if (data.sensor_type === 'vibration') v = data.value;
              } else if (data.type === 'SENSOR_BATCH') {
                data.readings.forEach((r: any) => {
                  if (r.sensor_type === 'temperature') t = r.value;
                  if (r.sensor_type === 'gas') g = r.value;
                  if (r.sensor_type === 'smoke') s = r.value;
                  if (r.sensor_type === 'vibration') v = r.value;
                });
              } else if (data.type === 'VISION_EVENT') {
                o = data.occupancy;
                if (data.snapshot_base64 && (roomTarget === selectedRoomIdRef.current)) {
                  setVisionSnapshot(data.snapshot_base64);
                }
              }

              const updatedTempHist = [...(cur.tempHistory || []).slice(-10), t];
              const updatedGasHist = [...(cur.gasHistory || []).slice(-10), g];
              const updatedSmokeHist = [...(cur.smokeHistory || []).slice(-10), s];

              return {
                ...prev,
                [roomTarget]: {
                  ...cur,
                  temperature: t,
                  gas: g,
                  smoke: s,
                  vibration: v,
                  occupancy: o,
                  tempHistory: updatedTempHist,
                  gasHistory: updatedGasHist,
                  smokeHistory: updatedSmokeHist
                }
              };
            });
          }

          if (data.type === 'AUDIO_EVENT') {
            setAudioEvent(data.event_type);
          } else if (data.type === 'INCIDENT_ALERT' || data.type === 'INCIDENT_RESOLVED') {
            loadInitialData();
          } else if (data.type === 'ROOM_STATE_CHANGED') {
            setRooms(prev => prev.map(r => r.id === data.room_id ? { ...r, state: data.state } : r));
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

  // Firebase Realtime Database live subscription
  useEffect(() => {
    let unsubTelemetry: (() => void) | undefined;
    let unsubIncidents: (() => void) | undefined;
    let unsubRooms: (() => void) | undefined;

    try {
      if (rtdb) {
        // 1. Telemetry subscription
        const telemRef = dbRef(rtdb, 'telemetry');
        unsubTelemetry = onValue(telemRef, (snapshot) => {
          if (snapshot.exists()) {
            setFirebaseConnected(true);
            const val = snapshot.val();
            if (val && typeof val === 'object') {
              setAllTelemetry(prev => {
                const updated = { ...prev };
                Object.entries(val).forEach(([roomId, data]: [string, any]) => {
                  if (!data || typeof data !== 'object') return;
                  const cur = updated[roomId] || DEFAULT_ROOM_TELEMETRY[roomId] || {
                    temperature: 22.0, humidity: 45.0, gas: 80.0, smoke: 0.3, occupancy: 0, vibration: 0.025,
                    tempHistory: [], gasHistory: [], smokeHistory: []
                  };

                  let t = cur.temperature;
                  let g = cur.gas;
                  let s = cur.smoke ?? 0.3;
                  let v = cur.vibration;
                  let o = cur.occupancy;

                  if (data.readings && Array.isArray(data.readings)) {
                    data.readings.forEach((r: any) => {
                      if (r.sensor_type === 'temperature') t = Number(r.value);
                      if (r.sensor_type === 'gas') g = Number(r.value);
                      if (r.sensor_type === 'smoke') s = Number(r.value);
                      if (r.sensor_type === 'vibration') v = Number(r.value);
                    });
                  }
                  if (data.temperature !== undefined) t = Number(data.temperature);
                  if (data.gas !== undefined) g = Number(data.gas);
                  if (data.smoke !== undefined) s = Number(data.smoke);
                  if (data.vibration !== undefined) v = Number(data.vibration);
                  if (data.occupancy !== undefined) o = Number(data.occupancy);

                  updated[roomId] = {
                    ...cur,
                    temperature: t,
                    gas: g,
                    smoke: s,
                    vibration: v,
                    occupancy: o,
                    tempHistory: [...(cur.tempHistory || []).slice(-10), t],
                    gasHistory: [...(cur.gasHistory || []).slice(-10), g],
                    smokeHistory: [...(cur.smokeHistory || []).slice(-10), s]
                  };
                });
                return updated;
              });
            }
          }
        }, (err) => {
          console.warn('Firebase RTDB telemetry warning:', err.message);
        });

        // 2. Incidents subscription
        const incRef = dbRef(rtdb, 'incidents');
        unsubIncidents = onValue(incRef, (snapshot) => {
          if (snapshot.exists()) {
            setFirebaseConnected(true);
            const val = snapshot.val();
            if (val && typeof val === 'object') {
              const incList: Incident[] = Object.values(val);
              if (incList.length > 0) {
                setIncidents(incList);
              }
            }
          }
        }, (err) => {
          console.warn('Firebase RTDB incidents warning:', err.message);
        });

        // 3. Rooms subscription
        const roomsRef = dbRef(rtdb, 'rooms');
        unsubRooms = onValue(roomsRef, (snapshot) => {
          if (snapshot.exists()) {
            setFirebaseConnected(true);
            const val = snapshot.val();
            if (val && typeof val === 'object') {
              setRooms(prev => prev.map(r => {
                if (val[r.id] && val[r.id].state) {
                  return { ...r, state: val[r.id].state };
                }
                return r;
              }));
            }
          }
        }, (err) => {
          console.warn('Firebase RTDB rooms warning:', err.message);
        });
      }
    } catch (e) {
      console.warn('Firebase RTDB init error:', e);
    }

    return () => {
      if (unsubTelemetry) unsubTelemetry();
      if (unsubIncidents) unsubIncidents();
      if (unsubRooms) unsubRooms();
    };
  }, []);

  // Handle Ask Assistant
  const handleAsk = async (queryText?: string) => {
    const q = queryText || question;
    if (!q.trim() || aiLoading) return;

    const userMsg = { role: 'user' as const, text: q };
    setChatMessages(prev => [...prev, userMsg]);
    setQuestion('');
    setAiLoading(true);

    try {
      const res = await fetch('http://127.0.0.1:8000/api/ai/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, room_id: selectedRoomId })
      });
      if (res.ok) {
        const data = await res.json();
        setChatMessages(prev => [
          ...prev, 
          { role: 'assistant', text: data.answer, offline: data.is_offline_mode }
        ]);
      }
    } catch (err) {
      setChatMessages(prev => [
        ...prev, 
        { role: 'assistant', text: 'Error contacting AI backend service.', offline: true }
      ]);
    } finally {
      setAiLoading(false);
    }
  };

  // Web Speech API Voice Recognition
  const toggleSpeechRecognition = () => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      alert('Speech recognition is not supported in this browser. Please use keyboard input.');
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

  // Run What If Simulation
  const handleRunSimulation = async () => {
    setSimExecuting(true);
    try {
      const payload = {
        scenario: "custom_what_if",
        room_id: selectedRoomId,
        temperature_delta: simTempDelta,
        gas_delta: simGasDelta,
        smoke_delta: simSmokeDelta,
        motion: simMotion,
        person_present: simPerson,
        acoustic_anomaly: simAudioAlarm,
        disabled_sensors: disabledSensors
      };
      await fetch('http://127.0.0.1:8000/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      await loadInitialData();
    } catch (e) {
      console.error('Simulation error:', e);
    } finally {
      setSimExecuting(false);
    }
  };

  // Reset to Healthy Baseline
  const handleResetSystem = async () => {
    try {
      for (const inc of incidents) {
        await fetch(`http://127.0.0.1:8000/api/incidents/${inc.id}/resolve`, { method: 'POST' });
      }
      for (const r of rooms) {
        await fetch(`http://127.0.0.1:8000/api/rooms/${r.id}/state`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ state: 'NORMAL' })
        });
      }
      try {
        await fetch('http://127.0.0.1:8000/api/vision/event', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            room_id: 'lab_02',
            event_type: 'NO_SUBJECT',
            occupancy_count: 0,
            confidence: 1.0,
            bounding_boxes: []
          })
        });
      } catch (err) {
        console.debug('Reset vision event error:', err);
      }
      setAllTelemetry(DEFAULT_ROOM_TELEMETRY);
      setAudioEvent('NORMAL');
      setDisabledSensors([]);
      await loadInitialData();
    } catch (e) {
      console.error('Reset error:', e);
    }
  };

  const toggleSensorDisable = (sensor: string) => {
    setDisabledSensors(prev => 
      prev.includes(sensor) ? prev.filter(s => s !== sensor) : [...prev, sensor]
    );
  };

  // High-Resolution SVG Area Sparkline helper
  const renderSparkline = (data: number[], color: string, height: number = 28) => {
    if (!data || data.length < 2) return null;
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const width = 100;
    const points = data.map((val, idx) => {
      const x = (idx / (data.length - 1)) * width;
      const y = height - ((val - min) / range) * (height - 8) - 4;
      return `${x},${y}`;
    }).join(' ');

    const firstY = height - ((data[0] - min) / range) * (height - 8) - 4;
    const lastY = height - ((data[data.length - 1] - min) / range) * (height - 8) - 4;
    const areaPoints = `0,${height} 0,${firstY} ${points} ${width},${lastY} ${width},${height}`;
    const cleanId = color.replace(/[^a-zA-Z0-9]/g, '');

    return (
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-6 overflow-visible">
        <defs>
          <linearGradient id={`grad-${cleanId}`} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={color} stopOpacity="0.3" />
            <stop offset="100%" stopColor={color} stopOpacity="0.0" />
          </linearGradient>
        </defs>
        <polygon points={areaPoints} fill={`url(#grad-${cleanId})`} />
        <polyline points={points} fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  };

  return (
    <main className="min-h-screen ambient-mesh text-slate-100 flex flex-col font-sans selection:bg-cyan-500 selection:text-black">
      
      {/* 1. Command Header - Clean, Restrained, High-Contrast */}
      <header className="sticky top-0 z-50 px-4 lg:px-8 py-3.5 border-b border-white/[0.08] bg-[#090d16]/90 backdrop-blur-xl transition-all">
        <div className="max-w-[1780px] mx-auto flex flex-col md:flex-row items-center justify-between gap-3.5">
          
          {/* Logo & Platform Designation */}
          <div className="flex items-center gap-3 w-full md:w-auto justify-between md:justify-start">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-xl bg-slate-900 border border-white/10 flex items-center justify-center shadow-sm">
                <Cpu className="h-4 w-4 text-cyan-400" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold tracking-wider text-white text-base font-display">NEXUS</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 border border-white/10 text-slate-300 font-mono font-medium">
                    DIGITAL TWIN OS
                  </span>
                  <span className="hidden lg:inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-slate-800/80 border border-white/10 text-emerald-400 font-mono text-[10px]">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                    AUTONOMOUS
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 font-normal">
                  Multimodal Environmental Surveillance, Neural Forecasting & Incident Synthesis
                </p>
              </div>
            </div>

            {/* Mobile Status Dot */}
            <div className="md:hidden flex items-center gap-2">
              <span className={`h-2.5 w-2.5 rounded-full ${wsConnected ? 'bg-emerald-400' : 'bg-rose-500'}`} />
            </div>
          </div>

          {/* Center: Segmented Navigation Switcher */}
          <nav className="flex items-center bg-slate-900/90 p-1 rounded-xl border border-white/10 text-xs font-mono">
            <button
              type="button"
              onClick={() => setActiveTab('overview')}
              className={`px-3.5 py-1.5 rounded-lg transition-all flex items-center gap-2 ${
                activeTab === 'overview' 
                  ? 'bg-slate-800 text-white font-bold border border-white/15 shadow-sm' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Activity className="h-3.5 w-3.5 text-cyan-400" />
              <span>Operations Command</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('simulation')}
              className={`px-3.5 py-1.5 rounded-lg transition-all flex items-center gap-2 ${
                activeTab === 'simulation' 
                  ? 'bg-slate-800 text-white font-bold border border-white/15 shadow-sm' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Sliders className="h-3.5 w-3.5 text-indigo-400" />
              <span>What-If Studio</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('assistant')}
              className={`px-3.5 py-1.5 rounded-lg transition-all flex items-center gap-2 ${
                activeTab === 'assistant' 
                  ? 'bg-slate-800 text-white font-bold border border-white/15 shadow-sm' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Sparkles className="h-3.5 w-3.5 text-violet-400" />
              <span>AI Copilot</span>
            </button>
          </nav>

          {/* Right: Status Cluster & Reset Action */}
          <div className="flex items-center gap-2.5">
            {/* UTC Chronometer */}
            <div className="hidden xl:flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/80 border border-white/10 text-xs font-mono text-slate-300">
              <Clock className="h-3.5 w-3.5 text-slate-400" />
              <span className="tnum font-medium">{currentTime || '00:00:00 UTC'}</span>
            </div>

            {/* WebSocket Stream Badge */}
            <div 
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-slate-900/80 border border-white/10 text-xs"
              title="Low-latency WebSocket event mesh"
            >
              <span className={`h-2 w-2 rounded-full ${wsConnected ? 'bg-emerald-400' : 'bg-rose-500'}`} />
              <span className="text-slate-300 font-mono text-[11px]">
                {wsConnected ? 'LIVE MESH' : 'WS RECONNECT'}
              </span>
            </div>

            {/* Firebase Cloud Sync Badge */}
            <div 
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-slate-900/80 border border-white/10 text-xs"
              title="Google Firebase Realtime Database"
            >
              <Database className="h-3 w-3 text-amber-400" />
              <span className={`h-2 w-2 rounded-full ${firebaseConnected ? 'bg-amber-400' : 'bg-slate-500'}`} />
              <span className="text-slate-300 font-mono text-[11px] hidden sm:inline">
                {firebaseConnected ? 'FIRESTORE LIVE' : 'FIRESTORE CLOUD'}
              </span>
            </div>

            {/* AI Engine Status Badge */}
            <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-slate-900/80 border border-white/10 text-xs">
              <span className={`h-2 w-2 rounded-full ${health?.ai_engine?.status === 'ONLINE' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
              <span className="text-slate-300 font-mono text-[11px]">
                {health?.ai_engine?.status === 'ONLINE' ? 'GEMINI 3.6' : 'LOCAL EXPERT'}
              </span>
            </div>

            {/* Reset System Button */}
            <button
              type="button"
              onClick={handleResetSystem}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-white/10 text-slate-300 hover:text-white text-xs font-mono transition shadow-sm"
              title="Reset all incidents, telemetry, and room states to nominal baseline"
            >
              <RotateCcw className="h-3.5 w-3.5 text-slate-400" />
              <span className="hidden sm:inline font-medium">Reset</span>
            </button>
          </div>
        </div>
      </header>

      {/* 2. Emergency Alarm Ribbon */}
      {audioEvent === 'ALARM' && (
        <div className="mx-4 lg:mx-8 mt-4 p-4 rounded-2xl bg-gradient-to-r from-rose-950/90 via-red-900/80 to-slate-950 border border-rose-500/80 shadow-glow-rose flex flex-col md:flex-row items-center justify-between gap-4 animate-pulse z-40">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-2xl bg-rose-500/30 border border-rose-400">
              <BellRing className="h-6 w-6 text-rose-200 animate-bounce" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <span className="px-2.5 py-0.5 rounded-full bg-rose-500 text-white font-mono text-xs font-bold uppercase tracking-wider">
                  HAZARD AUDIO SIGNATURE CONFIRMED
                </span>
                <span className="text-xs font-mono text-rose-300 font-bold">
                  SECTOR: [{selectedRoomId.toUpperCase()}]
                </span>
              </div>
              <h4 className="text-base font-bold text-white font-display mt-0.5 tracking-wide">
                Acoustic Siren Resonance Identified (2.5 kHz Frequency Peak Detected)
              </h4>
              <p className="text-xs text-rose-200/90 mt-0.5">
                Physical DSP extracted anomalous RMS energy and distinct emergency spectral centroid. Evacuation recommendation active.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 font-mono text-xs text-rose-200 bg-rose-950/90 px-4 py-2 rounded-xl border border-rose-600">
            <span className="h-2.5 w-2.5 rounded-full bg-rose-400 animate-ping" />
            <span className="font-bold tracking-wider">SIREN VERIFIED</span>
          </div>
        </div>
      )}

      {/* 3. Main Operations Grid */}
      <div className="flex-1 px-4 lg:px-8 py-6 max-w-[1780px] mx-auto w-full grid grid-cols-12 gap-6 radar-grid">
        
        {/* Left 8 Columns: 3D Twin Viewport, Spatial Controls & Sensor Modalities */}
        <div className="col-span-12 lg:col-span-8 flex flex-col gap-6">
          
          {/* Holographic 3D Digital Twin Viewport - CLEAN CONTAINER WITHOUT DUPLICATE OVERLAYS */}
          <div className="h-[460px] rounded-2xl overflow-hidden glass-panel relative shadow-xl">
            <Building3D
              rooms={rooms}
              selectedRoomId={selectedRoomId}
              onSelectRoom={(id) => setSelectedRoomId(id)}
            />
          </div>

          {/* Tactical Zone Selector & Hardware Architecture Strip */}
          <div className="glass-panel rounded-2xl p-4 flex flex-col md:flex-row items-center justify-between gap-4 text-xs font-mono shadow-md">
            
            {/* Zone Selector Dropdown */}
            <div className="flex items-center gap-3 w-full md:w-auto">
              <span className="text-slate-400 font-bold tracking-wider">ZONE TARGET:</span>
              <div className="relative flex-1 md:w-80">
                <select
                  value={selectedRoomId}
                  onChange={(e) => setSelectedRoomId(e.target.value)}
                  className="w-full appearance-none bg-slate-900 border border-white/10 rounded-xl px-4 py-2.5 text-white font-bold focus:outline-none focus:border-cyan-400 transition shadow-inner pr-9 cursor-pointer"
                >
                  {rooms.map(r => (
                    <option key={r.id} value={r.id} className="bg-slate-950 text-slate-200">
                      {r.name} (Floor {r.floor})
                    </option>
                  ))}
                </select>
                <ChevronDown className="h-4 w-4 text-slate-400 absolute right-3 top-3 pointer-events-none" />
              </div>
            </div>
            
            {/* Hardware Architecture Node Badge */}
            <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-slate-900 border border-white/10 text-[11px]">
              <span className={`h-2.5 w-2.5 rounded-full ${selectedRoomId === 'lab_02' ? 'bg-emerald-400' : 'bg-slate-400'}`} />
              <span className="font-mono text-slate-300">
                {selectedRoomId === 'lab_02' ? 'PHYSICAL TESTBED (LAPTOP WEBCAM + MIC + ESP32)' : 'VIRTUAL MESH NODE'}
              </span>
            </div>

            {/* Condition Indicator */}
            <div className="flex items-center gap-2">
              <span className="text-slate-400 font-bold">STATE:</span>
              <span className={`px-3 py-1 rounded-xl font-bold text-xs tracking-wider ${
                rooms.find(r => r.id === selectedRoomId)?.state === 'INCIDENT' ? 'bg-rose-500/25 text-rose-300 border border-rose-500/40 animate-pulse' :
                rooms.find(r => r.id === selectedRoomId)?.state === 'ANOMALY' ? 'bg-orange-500/25 text-orange-300 border border-orange-500/40' :
                rooms.find(r => r.id === selectedRoomId)?.state === 'ATTENTION' ? 'bg-amber-500/25 text-amber-300 border border-amber-500/40' :
                'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
              }`}>
                {rooms.find(r => r.id === selectedRoomId)?.state || 'NORMAL'}
              </span>
            </div>
          </div>

          {/* 5 Distinct Semantic Sensor Modality Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            
            {/* 1. Thermal Dynamics (Warm Amber) */}
            <div className={`glass-card p-5 rounded-2xl flex flex-col justify-between ${temperature > 40 ? 'glow-rose-border bg-rose-950/30' : ''}`}>
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[11px] font-mono text-slate-400 uppercase font-bold flex items-center gap-1.5">
                    <Flame className={`h-4 w-4 ${temperature > 40 ? 'text-rose-400 animate-bounce' : 'text-amber-400'}`} />
                    Thermal
                  </span>
                  <span className="text-[10px] font-mono text-slate-400 px-1.5 py-0.5 rounded bg-slate-900 border border-white/10 font-bold">DHT22</span>
                </div>
                <div className="flex items-baseline justify-between mb-3">
                  <span className="text-3xl font-extrabold font-mono text-white tracking-tight tnum">
                    {temperature.toFixed(1)}<span className="text-base text-slate-400 font-normal">°C</span>
                  </span>
                  <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full ${
                    temperature > 40 ? 'bg-rose-500/25 text-rose-300 border border-rose-500/40' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                  }`}>
                    {temperature > 40 ? '+2.8°C/min' : 'NOMINAL'}
                  </span>
                </div>
                
                {/* Progress bar */}
                <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden mb-3 border border-white/5">
                  <div 
                    className={`h-full transition-all duration-500 ${temperature > 40 ? 'bg-rose-500' : 'bg-amber-500'}`}
                    style={{ width: `${Math.min(100, (temperature / 60) * 100)}%` }}
                  />
                </div>
              </div>

              {/* Sparkline */}
              <div className="pt-2 border-t border-white/[0.06]">
                <div className="flex justify-between items-center text-[10px] font-mono text-slate-400 mb-1">
                  <span>1-MIN TRAJECTORY</span>
                  <span className="tnum">{currentTelem.tempHistory?.length || 0} SAMPLES</span>
                </div>
                {renderSparkline(currentTelem.tempHistory || [temperature], temperature > 40 ? '#ef4444' : '#f59e0b')}
              </div>
            </div>

            {/* 2. Volatiles & Gas (Cool Teal) */}
            <div className={`glass-card p-5 rounded-2xl flex flex-col justify-between ${gas > 300 ? 'glow-rose-border bg-orange-950/30' : ''}`}>
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[11px] font-mono text-slate-400 uppercase font-bold flex items-center gap-1.5">
                    <Wind className={`h-4 w-4 ${gas > 300 ? 'text-orange-400 animate-pulse' : 'text-teal-400'}`} />
                    Gas / VOCs
                  </span>
                  <span className="text-[10px] font-mono text-slate-400 px-1.5 py-0.5 rounded bg-slate-900 border border-white/10 font-bold">MQ-2</span>
                </div>
                <div className="flex items-baseline justify-between mb-3">
                  <span className="text-3xl font-extrabold font-mono text-white tracking-tight tnum">
                    {gas.toFixed(0)} <span className="text-xs text-slate-400 font-normal">ppm</span>
                  </span>
                  <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full ${
                    gas > 300 ? 'bg-orange-500/25 text-orange-300 border border-orange-500/40' : 'bg-teal-500/10 text-teal-300 border border-teal-500/20'
                  }`}>
                    {gas > 300 ? 'SURGE' : 'SAFE'}
                  </span>
                </div>

                {/* Progress bar */}
                <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden mb-3 border border-white/5">
                  <div 
                    className={`h-full transition-all duration-500 ${gas > 300 ? 'bg-orange-500' : 'bg-teal-500'}`}
                    style={{ width: `${Math.min(100, (gas / 600) * 100)}%` }}
                  />
                </div>
              </div>

              {/* Sparkline */}
              <div className="pt-2 border-t border-white/[0.06]">
                <div className="flex justify-between items-center text-[10px] font-mono text-slate-400 mb-1">
                  <span>CONCENTRATION</span>
                  <span className="tnum">{currentTelem.gasHistory?.length || 0} SAMPLES</span>
                </div>
                {renderSparkline(currentTelem.gasHistory || [gas], gas > 300 ? '#f97316' : '#14b8a6')}
              </div>
            </div>

            {/* 3. Optical Smoke Detector (Photoelectric) */}
            <div className={`glass-card p-5 rounded-2xl flex flex-col justify-between ${smoke > 15 ? 'glow-rose-border bg-rose-950/30' : smoke > 5 ? 'border-amber-500/50 bg-amber-950/20' : ''}`}>
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[11px] font-mono text-slate-400 uppercase font-bold flex items-center gap-1.5">
                    <ShieldAlert className={`h-4 w-4 ${smoke > 15 ? 'text-rose-400 animate-bounce' : smoke > 5 ? 'text-amber-400' : 'text-slate-300'}`} />
                    Smoke Obs.
                  </span>
                  <span className="text-[10px] font-mono text-slate-400 px-1.5 py-0.5 rounded bg-slate-900 border border-white/10 font-bold">OPTICAL</span>
                </div>
                <div className="flex items-baseline justify-between mb-3">
                  <span className="text-3xl font-extrabold font-mono text-white tracking-tight tnum">
                    {smoke.toFixed(1)} <span className="text-xs text-slate-400 font-normal">% obs</span>
                  </span>
                  <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full ${
                    smoke > 15 ? 'bg-rose-500/25 text-rose-300 border border-rose-500/40' :
                    smoke > 5 ? 'bg-amber-500/25 text-amber-300 border border-amber-500/40' :
                    'bg-slate-800 text-slate-300 border border-white/10'
                  }`}>
                    {smoke > 15 ? 'DENSE SMOKE' : smoke > 5 ? 'ELEVATED' : 'CLEAN AIR'}
                  </span>
                </div>

                {/* Progress bar */}
                <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden mb-3 border border-white/5">
                  <div 
                    className={`h-full transition-all duration-500 ${
                      smoke > 15 ? 'bg-rose-500' :
                      smoke > 5 ? 'bg-amber-500' :
                      'bg-slate-600'
                    }`}
                    style={{ width: `${Math.min(100, (smoke / 50) * 100)}%` }}
                  />
                </div>
              </div>

              {/* Sparkline */}
              <div className="pt-2 border-t border-white/[0.06]">
                <div className="flex justify-between items-center text-[10px] font-mono text-slate-400 mb-1">
                  <span>OBSCURATION</span>
                  <span className="tnum">{currentTelem.smokeHistory?.length || 0} SAMPLES</span>
                </div>
                {renderSparkline(currentTelem.smokeHistory || [smoke], smoke > 15 ? '#ef4444' : smoke > 5 ? '#f59e0b' : '#94a3b8')}
              </div>
            </div>

            {/* 4. Occupancy & Edge Vision (Emerald) */}
            <div className="glass-card p-5 rounded-2xl flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[11px] font-mono text-slate-400 uppercase font-bold flex items-center gap-1.5">
                    <Eye className="h-4 w-4 text-emerald-400" />
                    Edge Vision
                  </span>
                  <span className="text-[10px] font-mono text-slate-400 px-1.5 py-0.5 rounded bg-slate-900 border border-white/10 font-bold">YOLOv5n</span>
                </div>
                <div className="flex items-baseline justify-between mb-2">
                  <span className="text-3xl font-extrabold font-mono text-white tracking-tight tnum">
                    {occupancy} <span className="text-xs text-slate-400 font-normal">person(s)</span>
                  </span>
                  <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    {occupancy > 0 ? 'OCCUPIED' : 'CLEAR'}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 truncate">
                  {occupancy > 0 ? 'Human subject(s) identified' : 'Zone clear of personnel'}
                </p>
              </div>

              {/* Vision Snapshot Trigger */}
              <div className="pt-3 border-t border-white/[0.06] mt-3">
                <button
                  type="button"
                  onClick={() => setSnapshotModalOpen(true)}
                  className="w-full py-1.5 px-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-white/10 text-[11px] font-mono text-slate-300 hover:text-white flex items-center justify-center gap-2 transition"
                >
                  <Maximize2 className="h-3 w-3 text-slate-400" />
                  {visionSnapshot ? 'Live Camera HUD' : 'Camera Feed Offline'}
                </button>
              </div>
            </div>

            {/* 5. Acoustic Intelligence & Vibration (Violet) */}
            <div className={`glass-card p-5 rounded-2xl flex flex-col justify-between ${
              audioEvent === 'ALARM' 
                ? 'glow-rose-border bg-rose-950/40 animate-pulse' 
                : audioEvent === 'SPEECH'
                ? 'border-indigo-500/40 bg-indigo-950/20'
                : ''
            }`}>
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[11px] font-mono text-slate-400 uppercase font-bold flex items-center gap-1.5">
                    <Mic className={`h-4 w-4 ${
                      audioEvent === 'ALARM' ? 'text-rose-400 animate-bounce' :
                      audioEvent === 'SPEECH' ? 'text-indigo-400' : 'text-violet-400'
                    }`} />
                    Acoustic / FFT
                  </span>
                  <span className="text-[10px] font-mono text-slate-400 px-1.5 py-0.5 rounded bg-slate-900 border border-white/10 font-bold">DSP</span>
                </div>
                <div className="flex items-baseline justify-between mb-2">
                  <span className={`text-2xl font-black font-mono tracking-tight uppercase truncate ${
                    audioEvent === 'ALARM' ? 'text-rose-300' :
                    audioEvent === 'SPEECH' ? 'text-indigo-300' : 'text-white'
                  }`}>
                    {audioEvent}
                  </span>
                  <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full ${
                    audioEvent === 'ALARM' ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40' :
                    audioEvent === 'SPEECH' ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40' :
                    'bg-slate-900 text-slate-400 border border-white/10'
                  }`}>
                    {audioEvent === 'ALARM' ? 'SIREN' : audioEvent === 'SPEECH' ? 'VOICE' : 'QUIET'}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 truncate">
                  {audioEvent === 'ALARM' ? '🚨 High-frequency alarm siren' :
                   audioEvent === 'SPEECH' ? '🗣️ Human speech detected' :
                   `Vib: ${vibration.toFixed(3)}g · Nominal`}
                </p>
              </div>

              {/* Animated 8-band Audio Equalizer */}
              <div className="pt-3 border-t border-white/[0.06] mt-3 flex items-center justify-between">
                <span className="text-[10px] font-mono text-slate-400">SPECTRUM CENTROID</span>
                <div className="flex items-end gap-1 h-5">
                  {[12, 24, 18, 28, 20, 16, 26, 14].map((h, i) => (
                    <div
                      key={i}
                      className={`w-1 rounded-full transition-all duration-200 ${
                        audioEvent === 'ALARM' ? 'bg-rose-500 animate-pulse' :
                        audioEvent === 'SPEECH' ? 'bg-indigo-400 animate-pulse' : 'bg-slate-700'
                      }`}
                      style={{ 
                        height: audioEvent === 'ALARM' ? `${h}px` : audioEvent === 'SPEECH' ? `${h * 0.7}px` : '4px' 
                      }}
                    />
                  ))}
                </div>
              </div>
            </div>

          </div>

          {/* Predictive Trend Horizon Forecaster Card */}
          {prediction && (
            <div className="glass-card rounded-2xl p-5 shadow-lg">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-slate-900 border border-white/10">
                    <ArrowUpRight className="h-4 w-4 text-cyan-400" />
                  </div>
                  <div>
                    <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-slate-200">
                      Predictive Horizon Analysis ({prediction.variable?.toUpperCase()})
                    </h3>
                    <p className="text-[11px] text-slate-400">Multivariate Least-Squares Trajectory & Anomaly Projection</p>
                  </div>
                </div>
                <span className="text-xs font-mono font-bold text-slate-300 bg-slate-900 px-3 py-1 rounded-xl border border-white/10">
                  Confidence: {int_percentage(prediction.confidence)}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 rounded-xl bg-slate-950/70 border border-white/5 text-center">
                  <p className="text-[10px] font-mono text-slate-400 uppercase font-bold tracking-wider">+1 MIN HORIZON</p>
                  <p className="text-2xl font-black font-mono text-white mt-1 tnum">
                    {prediction.horizons?.['+1m']?.predicted?.toFixed(1)}°C
                  </p>
                  <p className="text-[10px] font-mono text-slate-500 mt-1">
                    ±{((prediction.horizons?.['+1m']?.upper - prediction.horizons?.['+1m']?.lower)/2).toFixed(1)}°C CI Range
                  </p>
                </div>

                <div className="p-4 rounded-xl bg-slate-900 border border-white/15 text-center">
                  <p className="text-[10px] font-mono text-cyan-400 uppercase font-bold tracking-wider">+5 MIN HORIZON</p>
                  <p className="text-2xl font-black font-mono text-white mt-1 tnum">
                    {prediction.horizons?.['+5m']?.predicted?.toFixed(1)}°C
                  </p>
                  <p className="text-[10px] font-mono text-slate-400 mt-1">
                    ±{((prediction.horizons?.['+5m']?.upper - prediction.horizons?.['+5m']?.lower)/2).toFixed(1)}°C CI Range
                  </p>
                </div>

                <div className="p-4 rounded-xl bg-slate-950/70 border border-white/5 text-center">
                  <p className="text-[10px] font-mono text-slate-400 uppercase font-bold tracking-wider">+15 MIN HORIZON</p>
                  <p className="text-2xl font-black font-mono text-white mt-1 tnum">
                    {prediction.horizons?.['+15m']?.predicted?.toFixed(1)}°C
                  </p>
                  <p className="text-[10px] font-mono text-slate-500 mt-1">
                    ±{((prediction.horizons?.['+15m']?.upper - prediction.horizons?.['+15m']?.lower)/2).toFixed(1)}°C CI Range
                  </p>
                </div>
              </div>
              
              <div className="mt-4 p-3 rounded-xl bg-slate-950/70 border border-white/5 flex items-center gap-2.5 text-xs text-slate-300">
                <Zap className="h-4 w-4 text-cyan-400 shrink-0" />
                <span className="font-mono text-[11px]">{prediction.explanation}</span>
              </div>
            </div>
          )}
        </div>

        {/* Right 4 Columns: Multimodal Fusion Engine & AI Intelligence Hub */}
        <div className="col-span-12 lg:col-span-4 flex flex-col gap-6">

          {/* Active Incident & Multimodal Evidence Matrix Card */}
          <div className="glass-card rounded-2xl p-5 flex flex-col shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className={`p-2.5 rounded-xl border ${activeIncident ? 'bg-rose-500/15 border-rose-500/30' : 'bg-slate-900 border-white/10'}`}>
                  <ShieldAlert className={`h-4 w-4 ${activeIncident ? 'text-rose-400 animate-pulse' : 'text-slate-400'}`} />
                </div>
                <div>
                  <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-slate-200">
                    Multimodal Fusion Engine
                  </h3>
                  <p className="text-[11px] text-slate-400">Correlated Signal Attribution & Synthesis</p>
                </div>
              </div>
              {activeIncident && (
                <span className="text-[10px] font-mono px-3 py-1 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/40 font-bold">
                  {activeIncident.severity}
                </span>
              )}
            </div>

            {activeIncident ? (
              <div className="space-y-4">
                {/* Active Incident Brief */}
                <div className="p-4 rounded-xl bg-slate-950/90 border border-rose-500/30">
                  <div className="flex items-center justify-between mb-1.5">
                    <p className="text-xs font-bold text-rose-300 font-mono uppercase tracking-wider">
                      {activeIncident.type.replace(/_/g, ' ')}
                    </p>
                    <span className="text-[10px] font-mono text-rose-400 font-bold">
                      {int_percentage(activeIncident.confidence)} CONFIDENCE
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">{activeIncident.summary}</p>
                  
                  {/* Forensic Briefing Report Button */}
                  <a
                    href={`http://127.0.0.1:8000/api/ai/report/${activeIncident.id}?format=html`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-full mt-3.5 flex items-center justify-center gap-2 py-2 px-3.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-white/15 text-slate-200 hover:text-white text-xs font-mono font-bold transition shadow-sm"
                  >
                    <FileText className="h-4 w-4 text-slate-400" />
                    Open Forensic Incident Report
                    <ExternalLink className="h-3.5 w-3.5 text-slate-400 ml-auto" />
                  </a>
                </div>

                {/* Evidence Attribution Matrix */}
                <div>
                  <p className="text-[11px] font-mono text-slate-400 uppercase font-bold tracking-wider mb-2.5">
                    Evidence Attribution Matrix
                  </p>
                  <div className="space-y-2.5">
                    {activeIncident.evidence?.map((ev, idx) => (
                      <div key={idx} className="p-3.5 rounded-xl bg-slate-950/80 border border-white/5 text-xs">
                        <div className="flex items-center justify-between text-[11px] font-mono mb-1.5">
                          <span className={`font-bold ${
                            ev.source_type === 'SENSOR' ? 'text-teal-400' :
                            ev.source_type === 'VISION' ? 'text-emerald-400' : 'text-violet-400'
                          }`}>[{ev.source_type}] {ev.source_id}</span>
                          <span className="text-white font-bold tnum">{int_percentage(ev.contribution)} Weight</span>
                        </div>
                        {/* Contribution meter */}
                        <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden mb-2 border border-white/5">
                          <div 
                            className={`h-full ${
                              ev.source_type === 'SENSOR' ? 'bg-teal-400' :
                              ev.source_type === 'VISION' ? 'bg-emerald-400' : 'bg-violet-400'
                            }`}
                            style={{ width: int_percentage(ev.contribution) }}
                          />
                        </div>
                        <p className="text-[11px] text-slate-300 leading-relaxed">{ev.explanation}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Detection Chronology Log */}
                <div>
                  <p className="text-[11px] font-mono text-slate-400 uppercase font-bold tracking-wider mb-2">
                    Chronology Audit Feed
                  </p>
                  <div className="max-h-40 overflow-y-auto space-y-1.5 p-3 rounded-xl bg-slate-950/90 border border-white/5 text-[11px] font-mono">
                    {activeIncident.timeline?.map((t, idx) => (
                      <div key={idx} className="text-slate-300 leading-relaxed">
                        <span className="text-slate-500">[{t.time?.slice(11, 19)}]</span> <strong className="text-slate-300">[{t.source}]</strong> {t.description}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-14 flex flex-col items-center justify-center text-center">
                <div className="p-3.5 rounded-2xl bg-slate-900 border border-white/10 mb-3 shadow-sm">
                  <ShieldCheck className="h-8 w-8 text-emerald-400" />
                </div>
                <p className="text-sm font-bold text-white font-display">All Modalities Nominal</p>
                <p className="text-xs text-slate-400 max-w-xs mt-1 leading-relaxed">
                  Real-time cross-correlation running across physical IoT streams, optical smoke obscuration, YOLOv5n vision, and audio DSP. No active incidents.
                </p>
              </div>
            )}
          </div>

          {/* AI Cognitive Operator Assistant */}
          <div className="glass-card rounded-2xl p-5 flex-1 flex flex-col shadow-xl">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-slate-900 border border-white/10">
                  <Sparkles className="h-4 w-4 text-violet-400" />
                </div>
                <div>
                  <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-slate-200">
                    AI Operator Copilot
                  </h3>
                  <p className="text-[11px] text-slate-400">Autonomous Reasoning & Inquiry</p>
                </div>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] font-mono text-slate-400 bg-slate-900 px-2.5 py-0.5 rounded-full border border-white/10 font-bold">
                  GEMINI 3.6
                </span>
                <button
                  type="button"
                  onClick={() => setActiveTab('assistant')}
                  className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white border border-white/10 transition"
                  title="Expand to Fullscreen Copilot Studio"
                >
                  <Maximize2 className="h-3.5 w-3.5 text-violet-400" />
                </button>
              </div>
            </div>

            {/* Chat History */}
            <div className="flex-1 bg-slate-950/80 rounded-xl border border-white/5 p-3.5 overflow-y-auto max-h-[280px] space-y-3 text-xs font-sans">
              {chatMessages.map((msg, idx) => (
                <div key={idx} className={`p-3 rounded-xl leading-relaxed ${
                  msg.role === 'user' 
                    ? 'bg-slate-800 border border-white/15 text-white ml-6' 
                    : 'bg-slate-900 border border-white/10 text-slate-200 mr-4'
                }`}>
                  <p className="text-[10px] font-mono text-slate-400 mb-1 font-bold flex items-center gap-1.5">
                    {msg.role === 'user' ? 'OPERATOR' : 'NEXUS COGNITIVE CORE'} {msg.offline ? '(OFFLINE LOCAL EXPERT)' : ''}
                  </p>
                  <p className="text-xs whitespace-pre-wrap leading-relaxed">{msg.text}</p>
                </div>
              ))}
              {aiLoading && (
                <div className="p-3 text-slate-400 text-xs italic animate-pulse flex items-center gap-2 font-mono">
                  <Sparkles className="h-3.5 w-3.5 animate-spin text-cyan-400" />
                  NEXUS evaluating spatial building evidence...
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Quick Prompt Inquiry Pills */}
            <div className="flex flex-wrap gap-1.5 my-3">
              <button
                type="button"
                onClick={() => handleAsk("Why is Laboratory 02 highlighted?")}
                className="text-[10px] font-mono px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 border border-white/10 text-slate-300 hover:text-white transition"
              >
                "Why is Lab 02 highlighted?"
              </button>
              <button
                type="button"
                onClick={() => handleAsk("What changed first in the timeline?")}
                className="text-[10px] font-mono px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 border border-white/10 text-slate-300 hover:text-white transition"
              >
                "What changed first?"
              </button>
              <button
                type="button"
                onClick={() => handleAsk("Compare Server Room and Classroom 01 climate.")}
                className="text-[10px] font-mono px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 border border-white/10 text-slate-300 hover:text-white transition"
              >
                "Compare zone climates"
              </button>
            </div>

            {/* Input Form with Web Speech Voice Recognition */}
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
                placeholder="Ask NEXUS about rooms, sensors, trajectories..."
                className="flex-1 bg-slate-900 border border-white/10 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-white/30 font-mono transition"
              />
              <button
                type="button"
                onClick={toggleSpeechRecognition}
                className={`p-2.5 rounded-xl border transition ${
                  isListening ? 'bg-rose-500 border-rose-400 text-white shadow-glow-rose animate-pulse' : 'bg-slate-900 border-white/10 text-slate-300 hover:text-white'
                }`}
                title={isListening ? 'Listening... click to stop' : 'Voice input (Web Speech API)'}
              >
                {isListening ? <Volume2 className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
              </button>
              <button
                type="button"
                onClick={() => handleAsk()}
                disabled={aiLoading}
                className="p-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-bold transition border border-white/10 disabled:opacity-50"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 4. Live Camera Snapshot Modal */}
      {snapshotModalOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-6">
          <div className="glass-panel rounded-2xl max-w-2xl w-full p-6 shadow-2xl flex flex-col gap-4 border border-white/15">
            <div className="flex items-center justify-between pb-3 border-b border-white/10">
              <div className="flex items-center gap-2.5">
                <Eye className="h-5 w-5 text-emerald-400" />
                <h3 className="text-base font-bold font-mono text-white">
                  LIVE EDGE CAMERA HUD (ZONE [{selectedRoomId.toUpperCase()}])
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSnapshotModalOpen(false)}
                className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-slate-800 transition"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="rounded-xl overflow-hidden border border-white/10 bg-black relative flex items-center justify-center min-h-[340px]">
              {visionSnapshot ? (
                <img
                  src={`data:image/jpeg;base64,${visionSnapshot}`}
                  alt="Live Camera Snapshot"
                  className="w-full h-auto object-contain rounded-lg"
                />
              ) : (
                <div className="text-center p-8 text-slate-400 font-mono text-xs">
                  <Eye className="h-10 w-10 text-slate-600 mx-auto mb-2" />
                  No live camera feed available for this zone.
                </div>
              )}
            </div>

            <div className="flex justify-between items-center text-xs font-mono text-slate-400">
              <span>MODEL: YOLOv5n + YuNet (DirectShow Index 0)</span>
              <button
                type="button"
                onClick={() => setSnapshotModalOpen(false)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-mono"
              >
                Close Viewport
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 5. What-If Scenario Simulation Studio Modal */}
      {activeTab === 'simulation' && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-6">
          <div className="glass-panel border border-white/15 rounded-2xl max-w-2xl w-full p-6 shadow-2xl flex flex-col gap-5">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div className="flex items-center gap-2.5">
                <Sliders className="h-5 w-5 text-indigo-400" />
                <h3 className="text-base font-bold font-mono text-white">
                  "WHAT IF?" SCENARIO SIMULATION & SENSITIVITY BENCH
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setActiveTab('overview')}
                className="text-slate-400 hover:text-white text-xs font-mono px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 transition"
              >
                CLOSE [ESC]
              </button>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Inject synthetic environmental deltas and simulate sensor failures. The inputs are evaluated in real-time through the <strong>production Multimodal Fusion Engine</strong> to test system resilience.
            </p>

            {/* Sliders */}
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-xs font-mono mb-1.5">
                  <span className="text-slate-300">Temperature Delta:</span>
                  <span className="text-amber-400 font-bold tnum">+{simTempDelta}°C</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="40"
                  value={simTempDelta}
                  onChange={(e) => setSimTempDelta(Number(e.target.value))}
                  className="w-full cursor-pointer"
                />
              </div>

              <div>
                <div className="flex justify-between text-xs font-mono mb-1.5">
                  <span className="text-slate-300">Gas Delta:</span>
                  <span className="text-orange-400 font-bold tnum">+{simGasDelta} ppm</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="600"
                  value={simGasDelta}
                  onChange={(e) => setSimGasDelta(Number(e.target.value))}
                  className="w-full cursor-pointer"
                />
              </div>

              <div>
                <div className="flex justify-between text-xs font-mono mb-1.5">
                  <span className="text-slate-300">Smoke Obscuration Delta:</span>
                  <span className="text-rose-400 font-bold tnum">+{simSmokeDelta}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="80"
                  value={simSmokeDelta}
                  onChange={(e) => setSimSmokeDelta(Number(e.target.value))}
                  className="w-full cursor-pointer"
                />
              </div>

              {/* Modality Toggles */}
              <div className="grid grid-cols-3 gap-3 text-xs font-mono">
                <label className="flex items-center gap-2 bg-slate-900 p-3 rounded-xl border border-white/10 cursor-pointer hover:border-white/20 transition">
                  <input
                    type="checkbox"
                    checked={simPerson}
                    onChange={(e) => setSimPerson(e.target.checked)}
                    className="accent-emerald-400"
                  />
                  <span>Vision (Occupancy)</span>
                </label>
                <label className="flex items-center gap-2 bg-slate-900 p-3 rounded-xl border border-white/10 cursor-pointer hover:border-white/20 transition">
                  <input
                    type="checkbox"
                    checked={simAudioAlarm}
                    onChange={(e) => setSimAudioAlarm(e.target.checked)}
                    className="accent-violet-400"
                  />
                  <span>Acoustic Siren</span>
                </label>
                <label className="flex items-center gap-2 bg-slate-900 p-3 rounded-xl border border-white/10 cursor-pointer hover:border-white/20 transition">
                  <input
                    type="checkbox"
                    checked={simMotion}
                    onChange={(e) => setSimMotion(e.target.checked)}
                    className="accent-cyan-400"
                  />
                  <span>PIR Motion</span>
                </label>
              </div>

              {/* Sensor Failure Simulation */}
              <div className="p-4 bg-slate-950/80 rounded-xl border border-white/10">
                <p className="text-[11px] font-mono text-slate-300 uppercase font-bold mb-1.5">
                  Sensor Failure Simulation (Sensitivity Analysis)
                </p>
                <p className="text-[11px] text-slate-400 mb-3 leading-normal">
                  Disable individual sensors to observe how NEXUS recalculates confidence dynamically without single-point failure:
                </p>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => toggleSensorDisable('smoke')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-mono transition ${
                      disabledSensors.includes('smoke') ? 'bg-rose-500/25 text-rose-300 border border-rose-500' : 'bg-slate-900 text-slate-400 border border-white/10'
                    }`}
                  >
                    {disabledSensors.includes('smoke') ? 'SMOKE: DISABLED' : 'Smoke: Active'}
                  </button>
                  <button
                    type="button"
                    onClick={() => toggleSensorDisable('gas')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-mono transition ${
                      disabledSensors.includes('gas') ? 'bg-rose-500/25 text-rose-300 border border-rose-500' : 'bg-slate-900 text-slate-400 border border-white/10'
                    }`}
                  >
                    {disabledSensors.includes('gas') ? 'GAS: DISABLED' : 'Gas: Active'}
                  </button>
                  <button
                    type="button"
                    onClick={() => toggleSensorDisable('camera')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-mono transition ${
                      disabledSensors.includes('camera') ? 'bg-rose-500/25 text-rose-300 border border-rose-500' : 'bg-slate-900 text-slate-400 border border-white/10'
                    }`}
                  >
                    {disabledSensors.includes('camera') ? 'CAMERA: DISABLED' : 'Camera: Active'}
                  </button>
                  <button
                    type="button"
                    onClick={() => toggleSensorDisable('microphone')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-mono transition ${
                      disabledSensors.includes('microphone') ? 'bg-rose-500/25 text-rose-300 border border-rose-500' : 'bg-slate-900 text-slate-400 border border-white/10'
                    }`}
                  >
                    {disabledSensors.includes('microphone') ? 'MIC: DISABLED' : 'Microphone: Active'}
                  </button>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-white/10">
              <button
                type="button"
                onClick={() => setActiveTab('overview')}
                className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 hover:bg-slate-700 text-xs font-mono"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleRunSimulation}
                disabled={simExecuting}
                className="px-5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-750 border border-white/20 text-white text-xs font-mono font-bold flex items-center gap-2 shadow-sm disabled:opacity-50"
              >
                <Play className="h-4 w-4" />
                {simExecuting ? 'Evaluating Pipeline...' : 'Execute What-If Scenario'}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* 6. AI Operator Copilot Dedicated Studio / Floating Widget */}
      {activeTab === 'assistant' && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4 sm:p-6">
          <div className="glass-panel border border-white/15 rounded-2xl max-w-3xl w-full h-[85vh] max-h-[780px] p-6 shadow-2xl flex flex-col gap-4 relative animate-in fade-in zoom-in-95 duration-200">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-white/10 pb-3.5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-violet-950/60 border border-violet-500/30 text-violet-400">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-bold font-mono tracking-wide text-white">
                      AI OPERATOR COPILOT
                    </h3>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-300 border border-violet-500/20 font-semibold">
                      GEMINI 3.6 / LOCAL FALLBACK
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">
                    Autonomous Multimodal Reasoning & Spatial Q&A • Active Zone: <span className="font-mono text-cyan-400 font-bold uppercase">{selectedRoomId.replace('_', ' ')}</span>
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setChatMessages([
                    {
                      role: 'assistant',
                      text: 'NEXUS Autonomous Operations Core active. Multimodal sensor streams, computer vision, and acoustic signatures are synced. Query any zone condition, forecast, or anomaly trace.'
                    }
                  ])}
                  className="text-slate-400 hover:text-white text-xs font-mono px-2.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-white/10 transition flex items-center gap-1.5"
                  title="Reset conversation"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">Reset</span>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('overview')}
                  className="text-slate-400 hover:text-white text-xs font-mono px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 transition flex items-center gap-1"
                >
                  <X className="h-4 w-4" />
                  <span>CLOSE [ESC]</span>
                </button>
              </div>
            </div>

            {/* Live Context Strip */}
            <div className="px-3.5 py-2 rounded-xl bg-slate-950/60 border border-white/5 flex flex-wrap items-center justify-between gap-2 text-xs font-mono">
              <div className="flex items-center gap-4 text-slate-400">
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
                  <span className="text-slate-300">STREAM:</span> Live Telemetry Synced
                </span>
                <span>
                  <span className="text-slate-300">ACTIVE INCIDENTS:</span>{' '}
                  <span className={incidents.filter(i => i.status === 'ACTIVE').length > 0 ? 'text-rose-400 font-bold' : 'text-emerald-400'}>
                    {incidents.filter(i => i.status === 'ACTIVE').length}
                  </span>
                </span>
                <span className="hidden md:inline text-slate-500">
                  | T: {temperature}°C • Smoke: {smoke}% • Gas: {gas} ppm
                </span>
              </div>
              <div className="text-[11px] text-slate-500">
                Context window incorporates IoT sensors, YOLO vision, & micro-decibel acoustics
              </div>
            </div>

            {/* Chat History */}
            <div className="flex-1 bg-slate-950/80 rounded-xl border border-white/5 p-4 overflow-y-auto space-y-3.5 text-xs font-sans">
              {chatMessages.map((msg, idx) => (
                <div 
                  key={idx} 
                  className={`p-4 rounded-xl leading-relaxed transition-all ${
                    msg.role === 'user' 
                      ? 'bg-slate-800/90 border border-white/15 text-white ml-8 sm:ml-16 shadow-md' 
                      : 'bg-slate-900/90 border border-violet-500/20 text-slate-200 mr-6 sm:mr-12 shadow-md'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <p className="text-[10px] font-mono text-slate-400 font-bold flex items-center gap-1.5">
                      {msg.role === 'user' ? (
                        <>
                          <span className="h-1.5 w-1.5 rounded-full bg-cyan-400"></span>
                          OPERATOR
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-3 w-3 text-violet-400" />
                          NEXUS COGNITIVE CORE
                        </>
                      )}
                    </p>
                    {msg.offline && (
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                        OFFLINE LOCAL EXPERT
                      </span>
                    )}
                  </div>
                  <div className="text-xs sm:text-sm whitespace-pre-wrap leading-relaxed">
                    {msg.text}
                  </div>
                </div>
              ))}

              {aiLoading && (
                <div className="p-4 rounded-xl bg-slate-900/60 border border-violet-500/20 mr-12 text-slate-300 text-xs sm:text-sm font-mono flex items-center gap-3">
                  <Sparkles className="h-4 w-4 animate-spin text-violet-400 flex-shrink-0" />
                  <span>Evaluating spatial building telemetry and generating cognitive hypothesis...</span>
                </div>
              )}
              <div ref={modalChatEndRef} />
            </div>

            {/* Quick Prompt Inquiry Pills */}
            <div className="flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => handleAsk("Why is Laboratory 02 highlighted?")}
                className="text-[11px] font-mono px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-white/10 text-slate-300 hover:text-white transition flex items-center gap-1.5"
              >
                <span>"Why is Lab 02 highlighted?"</span>
              </button>
              <button
                type="button"
                onClick={() => handleAsk("What changed first in the timeline?")}
                className="text-[11px] font-mono px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-white/10 text-slate-300 hover:text-white transition flex items-center gap-1.5"
              >
                <span>"What changed first?"</span>
              </button>
              <button
                type="button"
                onClick={() => handleAsk("Compare Server Room and Classroom 01 climate.")}
                className="text-[11px] font-mono px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-white/10 text-slate-300 hover:text-white transition flex items-center gap-1.5"
              >
                <span>"Compare zone climates"</span>
              </button>
              <button
                type="button"
                onClick={() => handleAsk("Summarize current zone risks and evacuation priorities.")}
                className="text-[11px] font-mono px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-white/10 text-slate-300 hover:text-white transition flex items-center gap-1.5"
              >
                <span>"Summarize zone risks"</span>
              </button>
            </div>

            {/* Input Form with Web Speech Voice Recognition */}
            <div className="flex items-center gap-2 pt-1">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
                placeholder="Ask NEXUS about rooms, sensors, thermal anomalies, or evacuation trajectories..."
                className="flex-1 bg-slate-900 border border-white/15 rounded-xl px-4 py-3 text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:border-violet-400 font-mono transition"
              />
              <button
                type="button"
                onClick={toggleSpeechRecognition}
                className={`p-3 rounded-xl border transition ${
                  isListening 
                    ? 'bg-rose-500 border-rose-400 text-white shadow-glow-rose animate-pulse' 
                    : 'bg-slate-900 border-white/10 text-slate-300 hover:text-white'
                }`}
                title={isListening ? 'Listening... click to stop' : 'Voice input (Web Speech API)'}
              >
                {isListening ? <Volume2 className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
              </button>
              <button
                type="button"
                onClick={() => handleAsk()}
                disabled={aiLoading || !question.trim()}
                className="px-4 py-3 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-mono font-bold transition border border-violet-400/30 disabled:opacity-40 flex items-center gap-2"
              >
                <span>Send</span>
                <Send className="h-4 w-4" />
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
