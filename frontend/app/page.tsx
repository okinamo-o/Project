'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  ShieldAlert, Eye, Mic, RotateCcw, Flame, Wind, Thermometer,
  ArrowUpRight, Send, FileText, Sliders, Play, Volume2,
  BellRing, ExternalLink, Sparkles, Maximize2, X,
  ShieldCheck, Sun, Moon, Building2, MessageSquare, CheckCircle2
} from 'lucide-react';
import Building3D, {
  RoomState,
  FACILITY_ROOM_CONFIGS,
} from '@/components/digital-twin/Building3D';
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

const QUICK_SCENARIOS = [
  { label: 'Fire & Smoke in Lab 02', room_id: 'lab_02', tempDelta: 26, gasDelta: 340, smokeDelta: 45, person: true, audioAlarm: true, motion: true },
  { label: 'Server Room Overheat', room_id: 'server_room', tempDelta: 24, gasDelta: 20, smokeDelta: 2, person: false, audioAlarm: false, motion: false },
  { label: 'Gas Leak in Lab 02', room_id: 'lab_02', tempDelta: 3, gasDelta: 400, smokeDelta: 5, person: true, audioAlarm: false, motion: true },
  { label: 'Normal Baseline', room_id: 'lab_02', tempDelta: 0, gasDelta: 0, smokeDelta: 0, person: false, audioAlarm: false, motion: false },
];

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
  const [selectedRoomId, setSelectedRoomId] = useState<string>('lab_02');
  const selectedRoomIdRef = useRef<string>(selectedRoomId);
  useEffect(() => {
    selectedRoomIdRef.current = selectedRoomId;
  }, [selectedRoomId]);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [firebaseConnected, setFirebaseConnected] = useState<boolean>(false);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [snapshotModalOpen, setSnapshotModalOpen] = useState<boolean>(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const [allTelemetry, setAllTelemetry] = useState<Record<string, RoomTelemetry>>(DEFAULT_ROOM_TELEMETRY);
  const [audioEvent, setAudioEvent] = useState<string>('NORMAL');
  const [audioRms, setAudioRms] = useState<number>(0.0015);
  const audioEventTimerRef = useRef<NodeJS.Timeout | null>(null);
  const [isWokwiActive, setIsWokwiActive] = useState<boolean>(false);
  const wokwiTimerRef = useRef<NodeJS.Timeout | null>(null);
  const [predictionVariable, setPredictionVariable] = useState<'temperature' | 'gas' | 'humidity'>('temperature');
  const [prediction, setPrediction] = useState<any>(null);
  const [visionSnapshot, setVisionSnapshot] = useState<string | null>(null);

  const [forensicExplanation, setForensicExplanation] = useState<string | null>(null);
  const [explainingIncidentId, setExplainingIncidentId] = useState<string | null>(null);

  const currentTelem = allTelemetry[selectedRoomId] || DEFAULT_ROOM_TELEMETRY[selectedRoomId] || {
    temperature: 22.0, humidity: 45.0, gas: 80.0, smoke: 0.3, occupancy: 0, vibration: 0.025,
    tempHistory: [22.0, 22.0, 22.0, 22.0, 22.0], gasHistory: [80, 80, 80, 80, 80], smokeHistory: [0.3, 0.3, 0.3, 0.3, 0.3]
  };
  const temperature = currentTelem.temperature;
  const humidity = currentTelem.humidity;
  const gas = currentTelem.gas;
  const smoke = currentTelem.smoke ?? 0.3;
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

  // Right bottom tool tab ('assistant' | 'simulation')
  const [rightToolTab, setRightToolTab] = useState<'assistant' | 'simulation'>('assistant');

  // Simulation state
  const [simTempDelta, setSimTempDelta] = useState<number>(20.0);
  const [simGasDelta, setSimGasDelta] = useState<number>(320.0);
  const [simSmokeDelta, setSimSmokeDelta] = useState<number>(35.0);
  const [simMotion, setSimMotion] = useState<boolean>(true);
  const [simPerson, setSimPerson] = useState<boolean>(true);
  const [simAudioAlarm, setSimAudioAlarm] = useState<boolean>(true);
  const [disabledSensors, setDisabledSensors] = useState<string[]>([]);
  const [simExecuting, setSimExecuting] = useState<boolean>(false);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
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
    incidents.find((i) => i.status === 'ACTIVE' && i.room_id === selectedRoomId) ||
    incidents.find((i) => i.status === 'ACTIVE') ||
    null;

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
      ws.onopen = () => setWsConnected(true);
      ws.onclose = () => setWsConnected(false);
      ws.onerror = () => setWsConnected(false);
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const roomTarget = data.room_id || 'lab_02';

          if (data.type === 'SENSOR_READING' || data.type === 'SENSOR_BATCH' || data.type === 'VISION_EVENT') {
            setAllTelemetry((prev) => {
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
                  vibration: v,
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
          } else if (data.type === 'SENSOR_BATCH' && data.room_id === 'lab_02') {
            if (data.is_wokwi) {
              setIsWokwiActive(true);
              if (wokwiTimerRef.current) clearTimeout(wokwiTimerRef.current);
              wokwiTimerRef.current = setTimeout(() => {
                setIsWokwiActive(false);
                wokwiTimerRef.current = null;
              }, 15000);
            }
          } else if (data.type === 'INCIDENT_ALERT' || data.type === 'INCIDENT_RESOLVED' || data.type === 'SIMULATION_RESULT') {
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
            if (snapshot.exists()) {
              setFirebaseConnected(true);
              const val = snapshot.val();
              if (val && typeof val === 'object') {
                setAllTelemetry((prev) => {
                  const updated = { ...prev };
                  Object.entries(val).forEach(([roomId, data]: [string, any]) => {
                    if (!data || typeof data !== 'object') return;
                    const cur = updated[roomId] || DEFAULT_ROOM_TELEMETRY[roomId] || {
                      temperature: 22.0, humidity: 45.0, gas: 80.0, smoke: 0.3, occupancy: 0, vibration: 0.025,
                      tempHistory: [], gasHistory: [], smokeHistory: []
                    };
                    let t = data.temperature !== undefined ? Number(data.temperature) : cur.temperature;
                    let g = data.gas !== undefined ? Number(data.gas) : cur.gas;
                    let s = data.smoke !== undefined ? Number(data.smoke) : (cur.smoke ?? 0.3);
                    let v = data.vibration !== undefined ? Number(data.vibration) : cur.vibration;
                    let o = data.occupancy !== undefined ? Number(data.occupancy) : cur.occupancy;

                    updated[roomId] = {
                      ...cur,
                      temperature: t,
                      gas: g,
                      smoke: s,
                      vibration: v,
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
          () => {}
        );

        const incRef = dbRef(rtdb, 'incidents');
        unsubIncidents = onValue(
          incRef,
          (snapshot) => {
            if (snapshot.exists()) {
              setFirebaseConnected(true);
              const val = snapshot.val();
              if (val && typeof val === 'object') {
                const incList: Incident[] = Object.values(val);
                if (incList.length > 0) setIncidents(incList);
              }
            }
          },
          () => {}
        );

        const roomsRef = dbRef(rtdb, 'rooms');
        unsubRooms = onValue(
          roomsRef,
          (snapshot) => {
            if (snapshot.exists()) {
              setFirebaseConnected(true);
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

    setChatMessages((prev) => [...prev, { role: 'user', text: q }]);
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
        setChatMessages((prev) => [
          ...prev,
          { role: 'assistant', text: data.answer, offline: data.is_offline_mode }
        ]);
      }
    } catch {
      setChatMessages((prev) => [
        ...prev,
        { role: 'assistant', text: 'Could not reach the AI service right now.', offline: true }
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
    try {
      await fetch(`http://127.0.0.1:8000/api/incidents/${incidentId}/resolve`, { method: 'POST' });
      setForensicExplanation(null);
      await loadInitialData();
    } catch (e) {
      console.error('Resolve error:', e);
    }
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

  const handleRunSimulation = async (customPreset?: typeof QUICK_SCENARIOS[number]) => {
    setSimExecuting(true);
    const targetRoom = customPreset ? customPreset.room_id : selectedRoomId;
    const tDelta = customPreset ? customPreset.tempDelta : simTempDelta;
    const gDelta = customPreset ? customPreset.gasDelta : simGasDelta;
    const sDelta = customPreset ? customPreset.smokeDelta : simSmokeDelta;
    const person = customPreset ? customPreset.person : simPerson;
    const alarm = customPreset ? customPreset.audioAlarm : simAudioAlarm;
    const motion = customPreset ? customPreset.motion : simMotion;

    if (customPreset) {
      setSelectedRoomId(customPreset.room_id);
      setSimTempDelta(customPreset.tempDelta);
      setSimGasDelta(customPreset.gasDelta);
      setSimSmokeDelta(customPreset.smokeDelta);
      setSimPerson(customPreset.person);
      setSimAudioAlarm(customPreset.audioAlarm);
      setSimMotion(customPreset.motion);
    }

    try {
      await fetch('http://127.0.0.1:8000/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario: 'custom_what_if',
          room_id: targetRoom,
          temperature_delta: tDelta,
          gas_delta: gDelta,
          smoke_delta: sDelta,
          motion,
          person_present: person,
          acoustic_anomaly: alarm,
          disabled_sensors: disabledSensors
        })
      });
      await loadInitialData();
    } catch (e) {
      console.error('Simulation error:', e);
    } finally {
      setSimExecuting(false);
    }
  };

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
      setAllTelemetry(DEFAULT_ROOM_TELEMETRY);
      setAudioEvent('NORMAL');
      setDisabledSensors([]);
      setForensicExplanation(null);
      await loadInitialData();
    } catch (e) {
      console.error('Reset error:', e);
    }
  };

  const toggleSensorDisable = (sensor: string) => {
    setDisabledSensors((prev) =>
      prev.includes(sensor) ? prev.filter((s) => s !== sensor) : [...prev, sensor]
    );
  };

  const renderSmoothSparkline = (data: number[], color: string) => {
    if (!data || data.length < 2) return null;
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = Math.max(max - min, 0.5);
    const width = 80;
    const height = 24;
    const points = data
      .map((val, idx) => {
        const x = (idx / (data.length - 1)) * width;
        const y = height - ((val - min) / range) * (height - 6) - 3;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');

    return (
      <div className="w-20 h-6 overflow-hidden flex items-center justify-end">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full overflow-hidden">
          <polyline
            points={points}
            fill="none"
            stroke={color}
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    );
  };

  const selectedRoomObj = rooms.find((r) => r.id === selectedRoomId) || rooms[0];
  const activeAlertCount = incidents.filter((i) => i.status === 'ACTIVE').length;
  const unitLabel = predictionVariable === 'temperature' ? '°C' : predictionVariable === 'gas' ? ' ppm' : '%';

  return (
    <main className="min-h-screen pb-10">
      {/* =====================================================================
          1. CLEAN TOP HEADER BAR
         ===================================================================== */}
      <header className="sticky top-0 z-40 border-b border-[var(--border-color)] bg-[var(--bg-surface)]/90 backdrop-blur-md">
        <div className="max-w-[1560px] mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          {/* Left: Brand & Clear Building Status */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2.5">
              <div className="h-9 w-9 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow-sm">
                <Building2 className="h-5 w-5" />
              </div>
              <div>
                <span className="font-display font-bold text-lg tracking-tight text-[var(--text-primary)]">
                  NEXUS
                </span>
                <span className="hidden sm:inline-block ml-2 text-xs text-[var(--text-muted)]">
                  Smart Building Monitor
                </span>
              </div>
            </div>

            <div className="h-5 w-[1px] bg-[var(--border-color)] hidden sm:block" />

            {/* Overall Building Status Pill */}
            {activeAlertCount > 0 ? (
              <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-red-500/10 border border-red-500/30 text-red-600 dark:text-red-400 text-xs font-semibold">
                <span className="h-2 w-2 rounded-full bg-red-500 animate-ping" />
                <span>{activeAlertCount} Active Alert{activeAlertCount > 1 ? 's' : ''}</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/25 text-emerald-600 dark:text-emerald-400 text-xs font-medium">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                <span>All 9 Rooms Normal</span>
              </div>
            )}
          </div>

          {/* Right: Connection Status, Theme Switcher & Reset */}
          <div className="flex items-center gap-2.5">
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[var(--bg-subtle)] border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
              <span className={`h-2 w-2 rounded-full ${wsConnected || firebaseConnected ? 'bg-emerald-500' : 'bg-amber-500'}`} />
              <span>{wsConnected ? 'Live Stream Connected' : firebaseConnected ? 'Cloud Synced' : 'Connecting...'}</span>
            </div>

            <button
              type="button"
              onClick={() => setTheme(theme === 'daylight' ? 'midnight' : 'daylight')}
              className="px-3 py-1.5 rounded-xl bg-[var(--bg-subtle)] hover:bg-[var(--bg-muted)] border border-[var(--border-color)] text-xs font-medium text-[var(--text-primary)] flex items-center gap-1.5 transition"
            >
              {theme === 'daylight' ? (
                <>
                  <Moon className="h-3.5 w-3.5 text-slate-600" />
                  <span>Dark Mode</span>
                </>
              ) : (
                <>
                  <Sun className="h-3.5 w-3.5 text-amber-400" />
                  <span>Light Mode</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={handleResetSystem}
              className="px-3.5 py-1.5 rounded-xl bg-[var(--bg-subtle)] hover:bg-[var(--bg-muted)] border border-[var(--border-color)] text-xs font-medium text-[var(--text-primary)] flex items-center gap-1.5 transition"
              title="Reset all rooms and alerts back to normal"
            >
              <RotateCcw className="h-3.5 w-3.5 text-[var(--text-secondary)]" />
              <span>Reset Building</span>
            </button>
          </div>
        </div>
      </header>

      {/* =====================================================================
          2. SINGLE, SIMPLE ROOM SELECTOR BAR
         ===================================================================== */}
      <div className="border-b border-[var(--border-color)] bg-[var(--bg-surface)]/60">
        <div className="max-w-[1560px] mx-auto px-4 sm:px-6 py-2.5 flex items-center gap-2 overflow-x-auto">
          <span className="text-xs font-semibold text-[var(--text-muted)] mr-1 shrink-0">
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

      {/* Emergency Siren Banner (Only shown when Siren is active) */}
      {audioEvent === 'ALARM' && (
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
          3. MAIN WORKSPACE (CLEAN 2-COLUMN LAYOUT)
         ===================================================================== */}
      <div className="max-w-[1560px] mx-auto px-4 sm:px-6 pt-5 grid grid-cols-12 gap-6">
        {/* -------------------------------------------------------------------
            LEFT 7 COLUMNS: 3D BUILDING + SELECTED ROOM SENSORS + FORECAST
           ------------------------------------------------------------------- */}
        <div className="col-span-12 lg:col-span-7 flex flex-col gap-5">
          {/* 1. Interactive 3D Building View */}
          <div className="h-[420px] studio-card p-2">
            <Building3D
              rooms={rooms}
              selectedRoomId={selectedRoomId}
              onSelectRoom={(id) => setSelectedRoomId(id)}
              telemetryByRoom={allTelemetry}
              theme={theme}
            />
          </div>

          {/* 2. Selected Room Live Sensor Cards (4 Clear Cards) */}
          <div>
            <div className="flex items-center justify-between mb-3 px-1 flex-wrap gap-2">
              <div className="flex items-center gap-2.5">
                <h2 className="font-display font-bold text-base text-[var(--text-primary)]">
                  {selectedRoomObj?.name} — Live Sensors
                </h2>
                {selectedRoomId === 'lab_02' && (
                  isWokwiActive ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 animate-pulse">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                      Wokwi Hardware Active
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                      Mesh Simulated
                    </span>
                  )
                )}
              </div>
              <span className="text-xs text-[var(--text-muted)]">
                Floor {selectedRoomObj?.floor} • {selectedRoomId === 'lab_02' ? 'Physical Sensor Node' : 'Virtual Room Node'}
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3.5">
              {/* Card 1: Temperature & Climate */}
              <div className="studio-card p-4 flex flex-col justify-between">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-[var(--text-secondary)] flex items-center gap-1.5">
                    <Thermometer className={`h-4 w-4 ${temperature > 30 ? 'text-red-500' : 'text-rose-500'}`} />
                    Temperature
                  </span>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                      temperature > 30
                        ? 'bg-red-500/15 text-red-600 dark:text-red-400'
                        : 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                    }`}
                  >
                    {temperature > 30 ? 'High' : 'Normal'}
                  </span>
                </div>
                <div className="flex items-end justify-between mt-1">
                  <div>
                    <div className="text-2xl font-display font-bold text-[var(--text-primary)] tnum">
                      {temperature.toFixed(1)}°C
                    </div>
                    <div className="text-[11px] text-[var(--text-muted)] mt-0.5">
                      Humidity: {humidity.toFixed(0)}% RH
                    </div>
                  </div>
                  {renderSmoothSparkline(currentTelem.tempHistory || [temperature], temperature > 30 ? '#ef4444' : '#f43f5e')}
                </div>
              </div>

              {/* Card 2: Gas & Air Quality */}
              <div className="studio-card p-4 flex flex-col justify-between">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-[var(--text-secondary)] flex items-center gap-1.5">
                    <Wind className={`h-4 w-4 ${gas > 300 ? 'text-amber-500' : 'text-teal-500'}`} />
                    Gas & Air
                  </span>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                      gas > 300
                        ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400'
                        : 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                    }`}
                  >
                    {gas > 300 ? 'Elevated' : 'Safe'}
                  </span>
                </div>
                <div className="flex items-end justify-between mt-1">
                  <div>
                    <div className="text-2xl font-display font-bold text-[var(--text-primary)] tnum">
                      {gas.toFixed(0)} <span className="text-xs font-normal text-[var(--text-muted)]">ppm</span>
                    </div>
                    <div className="text-[11px] text-[var(--text-muted)] mt-0.5">
                      MQ-2 Air Monitor
                    </div>
                  </div>
                  {renderSmoothSparkline(currentTelem.gasHistory || [gas], gas > 300 ? '#f59e0b' : '#14b8a6')}
                </div>
              </div>

              {/* Card 3: Optical Smoke Detector (Separated from Mic) */}
              <div className="studio-card p-4 flex flex-col justify-between">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-[var(--text-secondary)] flex items-center gap-1.5">
                    <Flame className={`h-4 w-4 ${smoke > 15 ? 'text-red-500 animate-pulse' : smoke > 5 ? 'text-amber-500' : 'text-orange-500'}`} />
                    Smoke Detector
                  </span>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                      smoke > 15
                        ? 'bg-red-500/15 text-red-600 dark:text-red-400'
                        : smoke > 5
                        ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400'
                        : 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                    }`}
                  >
                    {smoke > 15 ? 'Dense Smoke' : smoke > 5 ? 'Elevated' : 'Clean Air'}
                  </span>
                </div>
                <div className="mt-1">
                  <div className="text-2xl font-display font-bold text-[var(--text-primary)] tnum">
                    {smoke.toFixed(1)}% <span className="text-xs font-normal text-[var(--text-muted)]">smoke</span>
                  </div>
                  {/* Obscuration Level Bar Gauge */}
                  <div className="w-full bg-[var(--bg-subtle)] rounded-full h-2 overflow-hidden my-2 border border-[var(--border-color)]">
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
                  <div className="flex justify-between items-center text-[10px] text-[var(--text-muted)]">
                    <span>Photoelectric Sensor</span>
                    <span>Threshold: 15%</span>
                  </div>
                </div>
              </div>

              {/* Card 4: Acoustic Intelligence & Microphone (Separated from Smoke) */}
              <div className={`studio-card p-4 flex flex-col justify-between transition-all ${
                audioEvent === 'ALARM'
                  ? 'border-red-500 shadow-md shadow-red-500/10'
                  : audioEvent === 'SPEECH'
                  ? 'border-violet-500 shadow-md shadow-violet-500/10'
                  : ''
              }`}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-[var(--text-secondary)] flex items-center gap-1.5">
                    <Mic className={`h-4 w-4 ${
                      audioEvent === 'ALARM'
                        ? 'text-red-500 animate-pulse'
                        : audioEvent === 'SPEECH'
                        ? 'text-violet-500 animate-pulse'
                        : 'text-indigo-500'
                    }`} />
                    Microphone & VAD
                  </span>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                      audioEvent === 'ALARM'
                        ? 'bg-red-500/20 text-red-600 dark:text-red-400 animate-pulse font-bold'
                        : audioEvent === 'SPEECH'
                        ? 'bg-violet-500/20 text-violet-600 dark:text-violet-400 font-bold'
                        : audioEvent === 'IMPACT'
                        ? 'bg-amber-500/20 text-amber-600 dark:text-amber-400'
                        : 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                    }`}
                  >
                    {audioEvent === 'ALARM' ? 'Siren Alarm' : audioEvent === 'SPEECH' ? 'Voice Active' : audioEvent === 'IMPACT' ? 'Impact Noise' : 'Quiet Ambient'}
                  </span>
                </div>
                <div className="mt-1">
                  <div className="flex items-baseline justify-between">
                    <div className="text-2xl font-display font-bold text-[var(--text-primary)] tracking-wide">
                      {audioEvent}
                    </div>
                    <span className="text-[10px] font-mono font-medium text-[var(--text-muted)]">
                      {(audioRms * 1000).toFixed(1)} mVRMS
                    </span>
                  </div>
                  {/* Real-Time 5-Band Dynamic Equalizer Visualizer */}
                  <div className="flex items-end gap-1 h-3.5 mt-1.5 mb-1">
                    {[0.0018, 0.0035, 0.007, 0.015, 0.035].map((thresh, idx) => {
                      const active = audioRms >= thresh;
                      let barColor = 'bg-[var(--border-color)] h-1';
                      if (active) {
                        if (audioEvent === 'SPEECH') barColor = 'bg-violet-500 h-3.5';
                        else if (audioEvent === 'ALARM') barColor = 'bg-red-500 h-3.5';
                        else barColor = 'bg-emerald-500 h-2.5';
                      }
                      return (
                        <div
                          key={idx}
                          className={'w-2 rounded-full transition-all duration-100 ' + barColor}
                        />
                      );
                    })}
                  </div>
                  <div className="text-[11px] text-[var(--text-muted)] flex items-center gap-1.5">
                    <span className={`inline-block h-2 w-2 rounded-full ${
                      audioEvent === 'SPEECH' ? 'bg-violet-500 animate-ping' :
                      audioEvent === 'ALARM' ? 'bg-red-500 animate-ping' :
                      'bg-emerald-500'
                    }`} />
                    Real-Time Acoustic DSP (16kHz)
                  </div>
                </div>
              </div>

              {/* Card 5: People In Front & Live Camera (Click to open camera modal) */}
              <div
                onClick={() => setSnapshotModalOpen(true)}
                className="studio-card p-4 flex flex-col justify-between cursor-pointer group hover:border-emerald-500/60 hover:shadow-lg transition-all"
                title="Click to open 45 FPS Edge Camera Feed"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-[var(--text-secondary)] flex items-center gap-1.5">
                    <Eye className="h-4 w-4 text-emerald-500 group-hover:scale-110 transition-transform" />
                    People In Front
                  </span>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                      occupancy > 0
                        ? 'bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 font-bold'
                        : 'bg-slate-500/10 text-slate-500'
                    }`}
                  >
                    {occupancy > 0 ? 'OCCUPIED' : 'ZONE CLEAR'}
                  </span>
                </div>

                <div className="my-1">
                  <div className="text-3xl font-display font-extrabold text-[var(--text-primary)] tnum tracking-tight flex items-baseline gap-1.5">
                    {occupancy}
                    <span className="text-xs font-normal text-[var(--text-muted)]">
                      {occupancy === 1 ? 'person in front' : 'people in front'}
                    </span>
                  </div>
                  <p className="text-[11px] text-[var(--text-muted)] truncate mt-0.5">
                    {occupancy > 0 ? 'Human subject identified in camera view' : 'No subjects detected in zone'}
                  </p>
                </div>

                <div className="pt-2 border-t border-[var(--border-color)] mt-1 flex items-center justify-between text-xs text-emerald-600 dark:text-emerald-400 font-medium group-hover:text-emerald-500">
                  <span className="flex items-center gap-1 text-[11px]">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-ping"></span>
                    45 FPS Live Feed
                  </span>
                  <span className="flex items-center gap-1 text-[11px] text-[var(--text-secondary)] group-hover:text-[var(--text-primary)]">
                    <Maximize2 className="h-3 w-3" /> Open Camera
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* 3. 15-Minute Forecast Card */}
          <div className="studio-card p-5">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-400">
                  <ArrowUpRight className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="font-display font-bold text-sm text-[var(--text-primary)]">
                    15-Minute Forecast — {selectedRoomObj?.name}
                  </h3>
                  <p className="text-xs text-[var(--text-muted)]">
                    Predicted short-term trend based on recent sensor readings
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-1 bg-[var(--bg-subtle)] p-1 rounded-xl border border-[var(--border-color)] text-xs">
                {(['temperature', 'gas', 'humidity'] as const).map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => setPredictionVariable(v)}
                    className={`px-3 py-1 rounded-lg font-medium capitalize transition ${
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

            <div className="grid grid-cols-3 gap-3">
              {(['+1m', '+5m', '+15m'] as const).map((horizon) => {
                const hData = prediction?.horizons?.[horizon];
                const predVal =
                  hData?.predicted ??
                  (predictionVariable === 'temperature' ? temperature : predictionVariable === 'gas' ? gas : humidity);
                const label = horizon === '+1m' ? 'In 1 Minute' : horizon === '+5m' ? 'In 5 Minutes' : 'In 15 Minutes';

                return (
                  <div key={horizon} className="studio-subcard p-3.5 text-center">
                    <div className="text-xs text-[var(--text-muted)] font-medium">{label}</div>
                    <div className="text-xl font-display font-bold text-[var(--text-primary)] mt-1 tnum">
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
            RIGHT 5 COLUMNS: SAFETY STATUS & AI / SIMULATOR TOOLS
           ------------------------------------------------------------------- */}
        <div className="col-span-12 lg:col-span-5 flex flex-col gap-5">
          {/* 1. Safety & Active Alert Card */}
          <div className="studio-card p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-display font-bold text-base text-[var(--text-primary)] flex items-center gap-2">
                <ShieldAlert className={`h-5 w-5 ${activeIncident ? 'text-red-500' : 'text-emerald-500'}`} />
                Safety & Alert Status
              </h2>
              {activeIncident && (
                <span className="px-2.5 py-0.5 rounded-full bg-red-500/15 text-red-600 dark:text-red-400 text-xs font-bold">
                  {activeIncident.severity}
                </span>
              )}
            </div>

            {activeIncident ? (
              <div className="space-y-4">
                <div className="p-4 rounded-2xl bg-red-500/10 border border-red-500/25">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-display font-bold text-sm text-red-600 dark:text-red-400">
                      {activeIncident.type.replace(/_/g, ' ')}
                    </span>
                    <span className="text-xs font-semibold text-red-600 dark:text-red-400">
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
                      Why this alert triggered:
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
              <div className="studio-subcard p-5 flex items-center gap-4">
                <div className="p-3 rounded-2xl bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
                  <ShieldCheck className="h-7 w-7" />
                </div>
                <div>
                  <div className="font-display font-bold text-sm text-[var(--text-primary)]">
                    Everything Looks Good
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] mt-0.5 leading-relaxed">
                    No active safety alerts. Temperature, air quality, camera, and audio sensors are all within normal ranges.
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* 2. Interactive Assistant & Scenario Simulator Card */}
          <div className="studio-card p-5 flex-1 flex flex-col">
            {/* Simple 2-Tab Switcher */}
            <div className="flex items-center gap-2 p-1 rounded-xl bg-[var(--bg-subtle)] border border-[var(--border-color)] mb-4">
              <button
                type="button"
                onClick={() => setRightToolTab('assistant')}
                className={`flex-1 py-2 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 transition ${
                  rightToolTab === 'assistant'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }`}
              >
                <MessageSquare className="h-3.5 w-3.5" />
                <span>AI Assistant</span>
              </button>
              <button
                type="button"
                onClick={() => setRightToolTab('simulation')}
                className={`flex-1 py-2 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 transition ${
                  rightToolTab === 'simulation'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }`}
              >
                <Sliders className="h-3.5 w-3.5" />
                <span>Scenario Simulator</span>
              </button>
            </div>

            {rightToolTab === 'assistant' ? (
              <div className="flex-1 flex flex-col">
                {/* Chat Messages */}
                <div className="flex-1 studio-subcard p-3.5 overflow-y-auto max-h-[290px] space-y-3">
                  {chatMessages.map((msg, idx) => (
                    <div
                      key={idx}
                      className={`p-3 rounded-2xl text-xs leading-relaxed ${
                        msg.role === 'user'
                          ? 'bg-blue-600 text-white ml-8'
                          : 'bg-[var(--bg-surface)] border border-[var(--border-color)] text-[var(--text-primary)] mr-6'
                      }`}
                    >
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
                <div className="flex flex-wrap gap-1.5 my-3">
                  {[
                    'Why is Lab 02 highlighted?',
                    'Are all rooms safe right now?',
                    'Compare Server Room and Classroom 01'
                  ].map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => handleAsk(prompt)}
                      className="text-xs px-3 py-1.5 rounded-full bg-[var(--bg-subtle)] hover:bg-[var(--bg-muted)] border border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>

                {/* Chat Input */}
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
                    placeholder="Ask a question about any room..."
                    className="flex-1 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl px-3.5 py-2.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-blue-500"
                  />
                  <button
                    type="button"
                    onClick={toggleSpeechRecognition}
                    className={`p-2.5 rounded-xl border transition ${
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
                    className="px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5 transition disabled:opacity-50"
                  >
                    <Send className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ) : (
              /* SCENARIO SIMULATOR TAB */
              <div className="space-y-4">
                <p className="text-xs text-[var(--text-secondary)]">
                  Test how the building responds to emergencies. Pick a quick scenario below or adjust the sliders for <strong>{selectedRoomObj?.name}</strong>:
                </p>

                {/* Quick Preset Buttons */}
                <div className="grid grid-cols-2 gap-2">
                  {QUICK_SCENARIOS.map((preset) => (
                    <button
                      key={preset.label}
                      type="button"
                      onClick={() => handleRunSimulation(preset)}
                      disabled={simExecuting}
                      className="p-2.5 rounded-xl bg-[var(--bg-subtle)] hover:bg-[var(--bg-muted)] border border-[var(--border-color)] text-left text-xs font-semibold text-[var(--text-primary)] transition flex items-center justify-between"
                    >
                      <span>{preset.label}</span>
                      <Play className="h-3 w-3 text-blue-500 shrink-0" />
                    </button>
                  ))}
                </div>

                {/* Custom Sliders */}
                <div className="studio-subcard p-3.5 space-y-3">
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-[var(--text-secondary)]">Add Heat</span>
                      <span className="font-semibold text-[var(--text-primary)]">+{simTempDelta}°C</span>
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
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-[var(--text-secondary)]">Add Gas</span>
                      <span className="font-semibold text-[var(--text-primary)]">+{simGasDelta} ppm</span>
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
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-[var(--text-secondary)]">Add Smoke</span>
                      <span className="font-semibold text-[var(--text-primary)]">+{simSmokeDelta}%</span>
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
                </div>

                {/* Optional: Turn Off Sensors to test backup resilience */}
                <div>
                  <div className="text-xs font-medium text-[var(--text-secondary)] mb-1.5">
                    Test Sensor Failure (Click to turn off a sensor):
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {(['smoke', 'gas', 'camera', 'microphone'] as const).map((sensor) => {
                      const isOff = disabledSensors.includes(sensor);
                      return (
                        <button
                          key={sensor}
                          type="button"
                          onClick={() => toggleSensorDisable(sensor)}
                          className={`px-3 py-1 rounded-lg text-xs font-medium capitalize border transition ${
                            isOff
                              ? 'bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/30'
                              : 'bg-[var(--bg-subtle)] text-[var(--text-secondary)] border-[var(--border-color)]'
                          }`}
                        >
                          {sensor}: {isOff ? 'Off' : 'On'}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => handleRunSimulation()}
                  disabled={simExecuting}
                  className="w-full py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-sm transition disabled:opacity-50"
                >
                  <Play className="h-3.5 w-3.5 fill-current" />
                  <span>{simExecuting ? 'Running Simulation...' : 'Run Custom Simulation'}</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* =====================================================================
          4. LIVE CAMERA MODAL
         ===================================================================== */}
      {snapshotModalOpen && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="studio-card max-w-2xl w-full p-5 flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h3 className="font-display font-bold text-base text-[var(--text-primary)] flex items-center gap-2">
                <Eye className="h-5 w-5 text-emerald-500" />
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

            <div className="rounded-xl overflow-hidden bg-black flex items-center justify-center min-h-[340px]">
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
