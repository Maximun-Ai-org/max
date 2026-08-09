"""
Generador web offline-first — HTML/CSS/JS local.
Crea interfaces web servidas desde el dispositivo.
"""
import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime

logger = logging.getLogger("maximun.frontend")


class OfflineWebGenerator:
    """Genera interfaces web estáticas completas sin conexión."""

    BASE_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --primary: #2563eb;
            --bg: #0f172a;
            --surface: #1e293b;
            --text: #e2e8f0;
            --accent: #38bdf8;
            --success: #22c55e;
            --warning: #f59e0b;
            --error: #ef4444;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 1rem; }}
        .card {{
            background: var(--surface);
            border-radius: 12px;
            padding: 1.5rem;
            margin: 1rem 0;
            border: 1px solid #334155;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem;
            background: var(--surface);
            border-bottom: 1px solid #334155;
        }}
        .btn {{
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: opacity 0.2s;
        }}
        .btn:hover {{ opacity: 0.85; }}
        .btn-primary {{ background: var(--primary); color: white; }}
        .btn-success {{ background: var(--success); color: white; }}
        .btn-warning {{ background: var(--warning); color: #1e293b; }}
        .btn-danger {{ background: var(--error); color: white; }}
        .status {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.85rem;
        }}
        .status-online {{ background: #166534; color: #86efac; }}
        .status-offline {{ background: #991b1b; color: #fca5a5; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }}
        .metric {{
            text-align: center;
            padding: 1.5rem;
        }}
        .metric-value {{ font-size: 2.5rem; font-weight: 700; color: var(--accent); }}
        .metric-label {{ color: #94a3b8; margin-top: 0.5rem; }}
        .chat-box {{
            height: 400px;
            overflow-y: auto;
            padding: 1rem;
            background: #0f172a;
            border-radius: 8px;
            margin: 1rem 0;
        }}
        .chat-msg {{
            padding: 0.75rem 1rem;
            margin: 0.5rem 0;
            border-radius: 12px;
            max-width: 80%;
        }}
        .chat-user {{
            background: var(--primary);
            margin-left: auto;
            text-align: right;
        }}
        .chat-agent {{
            background: var(--surface);
            border: 1px solid #334155;
        }}
        .input-row {{
            display: flex;
            gap: 0.5rem;
            margin-top: 1rem;
        }}
        .input-row input {{
            flex: 1;
            padding: 0.75rem;
            border: 1px solid #334155;
            border-radius: 8px;
            background: #0f172a;
            color: var(--text);
            font-size: 1rem;
        }}
        textarea {{
            width: 100%;
            padding: 0.75rem;
            border: 1px solid #334155;
            border-radius: 8px;
            background: #0f172a;
            color: var(--text);
            font-size: 0.9rem;
            resize: vertical;
            min-height: 100px;
        }}
        .iot-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 1rem;
        }}
        .iot-device {{
            text-align: center;
            padding: 1rem;
            border-radius: 12px;
            cursor: pointer;
            transition: transform 0.2s;
        }}
        .iot-device:hover {{ transform: scale(1.05); }}
        .iot-device.on {{ background: #166534; border: 2px solid var(--success); }}
        .iot-device.off {{ background: #1e293b; border: 2px solid #475569; }}
        .iot-icon {{ font-size: 2rem; margin-bottom: 0.5rem; }}
        .iot-name {{ font-size: 0.8rem; color: #94a3b8; }}
        .iot-status {{ font-size: 0.7rem; margin-top: 0.25rem; }}
        @media (max-width: 640px) {{
            .grid {{ grid-template-columns: 1fr; }}
            .header {{ flex-direction: column; gap: 0.5rem; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 {title}</h1>
        <span class="status status-online">● Online</span>
    </div>
    <div class="container">
        {content}
    </div>
    {scripts}
</body>
</html>"""

    def __init__(self, output_dir: str = None):
        self.output_dir = Path(output_dir or "web")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_chat_page(self, title: str = "Máximun Chat") -> str:
        """Genera página de chat interactivo."""
        content = """
        <div class="card">
            <div class="chat-box" id="chatBox"></div>
            <div class="input-row">
                <input type="text" id="msgInput" placeholder="Escribe tu mensaje..." 
                       onkeypress="if(event.key==='Enter')sendMsg()">
                <button class="btn btn-primary" onclick="sendMsg()">Enviar</button>
                <button class="btn btn-success" onclick="startVoice()">🎤</button>
            </div>
        </div>
        <div class="card">
            <h3>Estado del Sistema</h3>
            <div class="grid" id="statusGrid"></div>
        </div>"""
        
        scripts = """
        <script>
        const API = 'http://127.0.0.1:8080';
        
        async function sendMsg() {
            const input = document.getElementById('msgInput');
            const msg = input.value.trim();
            if (!msg) return;
            
            addChat('user', msg);
            input.value = '';
            
            try {
                const res = await fetch(API + '/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: msg})
                });
                const data = await res.json();
                addChat('agent', data.response || 'Sin respuesta');
            } catch(e) {
                addChat('agent', '⚠ Error de conexión con el agente');
            }
        }
        
        function addChat(role, text) {
            const box = document.getElementById('chatBox');
            const div = document.createElement('div');
            div.className = 'chat-msg chat-' + role;
            div.textContent = text;
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
        }
        
        async function loadStatus() {
            try {
                const res = await fetch(API + '/status');
                const data = await res.json();
                const grid = document.getElementById('statusGrid');
                grid.innerHTML = '';
                const metrics = [
                    {label: 'Modelos', value: data.hrm?.models_available?.length || 0},
                    {label: 'HRM', value: data.hrm?.hrm_enabled ? 'Activo' : 'Inactivo'},
                    {label: 'Memoria', value: data.memory?.short_term?.total_sessions || 0 + ' sesiones'},
                    {label: 'Tiempo', value: new Date().toLocaleTimeString()},
                ];
                metrics.forEach(m => {
                    const card = document.createElement('div');
                    card.className = 'card metric';
                    card.innerHTML = '<div class="metric-value">' + m.value + '</div><div class="metric-label">' + m.label + '</div>';
                    grid.appendChild(card);
                });
            } catch(e) {
                document.getElementById('statusGrid').innerHTML = '<p style="color:var(--warning)">API no disponible</p>';
            }
        }
        
        function startVoice() {
            alert('Modo voz: conecta el micrófono y ejecuta python3 maximun.py --voice');
        }
        
        loadStatus();
        setInterval(loadStatus, 10000);
        </script>"""
        
        html = self.BASE_TEMPLATE.format(title=title, content=content, scripts=scripts)
        path = self.output_dir / "chat.html"
        path.write_text(html)
        return str(path)

    def generate_dashboard(self, title: str = "Máximun Dashboard") -> str:
        """Genera dashboard de sistema IoT/domótica."""
        content = """
        <div class="grid">
            <div class="card metric">
                <div class="metric-value" id="cpuTemp">--°C</div>
                <div class="metric-label">CPU Temp</div>
            </div>
            <div class="card metric">
                <div class="metric-value" id="ramUsage">--%</div>
                <div class="metric-label">RAM Uso</div>
            </div>
            <div class="card metric">
                <div class="metric-value" id="diskUsage">--%</div>
                <div class="metric-label">Disco Uso</div>
            </div>
            <div class="card metric">
                <div class="metric-value" id="uptime">--</div>
                <div class="metric-label">Uptime</div>
            </div>
        </div>
        <div class="card">
            <h3>🏠 Dispositivos IoT</h3>
            <div class="iot-grid" id="iotGrid"></div>
        </div>
        <div class="card">
            <h3>📊 Logs Recientes</h3>
            <textarea id="logs" rows="8" readonly></textarea>
        </div>"""
        
        scripts = """
        <script>
        const API = 'http://127.0.0.1:8080';
        const devices = [
            {id: 'light1', icon: '💡', name: 'Luz Sala', state: false},
            {id: 'light2', icon: '💡', name: 'Luz Cocina', state: false},
            {id: 'fan1', icon: '🌀', name: 'Ventilador', state: false},
            {id: 'temp1', icon: '🌡️', name: 'Temperatura', state: true},
            {id: 'door1', icon: '🚪', name: 'Puerta', state: false},
            {id: 'cam1', icon: '📷', name: 'Cámara', state: false},
        ];
        
        function renderDevices() {
            const grid = document.getElementById('iotGrid');
            grid.innerHTML = devices.map(d => 
                '<div class="iot-device ' + (d.state ? 'on' : 'off') + '" onclick="toggleDevice(\\'' + d.id + '\\')">' +
                '<div class="iot-icon">' + d.icon + '</div>' +
                '<div class="iot-name">' + d.name + '</div>' +
                '<div class="iot-status">' + (d.state ? '🟢 ON' : '⚫ OFF') + '</div>' +
                '</div>'
            ).join('');
        }
        
        function toggleDevice(id) {
            const dev = devices.find(d => d.id === id);
            if (dev) { dev.state = !dev.state; renderDevices(); }
        }
        
        async function updateMetrics() {
            try {
                const res = await fetch(API + '/status');
                const data = await res.json();
                document.getElementById('uptime').textContent = new Date().toLocaleTimeString();
            } catch(e) {}
        }
        
        renderDevices();
        updateMetrics();
        setInterval(updateMetrics, 5000);
        </script>"""
        
        html = self.BASE_TEMPLATE.format(title=title, content=content, scripts=scripts)
        path = self.output_dir / "dashboard.html"
        path.write_text(html)
        return str(path)

    def generate_iot_control(self, title: str = "Máximun IoT") -> str:
        """Genera panel de control IoT."""
        content = """
        <div class="card">
            <h3>⚡ Control de Dispositivos</h3>
            <div class="iot-grid" id="deviceGrid"></div>
        </div>
        <div class="card">
            <h3>📜 Reglas de Automatización</h3>
            <textarea id="rules" placeholder="Escribe reglas en lenguaje natural...&#10;Ejemplo: Si la temperatura supera 30°C, encender ventilador"></textarea>
            <button class="btn btn-primary" onclick="saveRules()" style="margin-top:0.5rem">Guardar Reglas</button>
        </div>
        <div class="card">
            <h3>⏰ Temporizadores</h3>
            <div id="timers"></div>
            <button class="btn btn-success" onclick="addTimer()" style="margin-top:0.5rem">+ Temporizador</button>
        </div>"""
        
        scripts = """
        <script>
        const devices = [
            {id:'relay1', icon:'💡', name:'Relé 1', gpio:17, state:false},
            {id:'relay2', icon:'💡', name:'Relé 2', gpio:27, state:false},
            {id:'relay3', icon:'🌀', name:'Relé 3', gpio:22, state:false},
            {id:'relay4', icon:'🔊', name:'Relé 4', gpio:23, state:false},
            {id:'sensor1', icon:'🌡️', name:'Temp Sensor', gpio:4, state:true},
            {id:'sensor2', icon:'💧', name:'Humedad', gpio:14, state:true},
        ];
        
        function render() {
            document.getElementById('deviceGrid').innerHTML = devices.map(d =>
                '<div class="iot-device ' + (d.state?'on':'off') + '" onclick="toggle(\\'' + d.id + '\\')">' +
                '<div class="iot-icon">' + d.icon + '</div>' +
                '<div class="iot-name">' + d.name + '</div>' +
                '<div class="iot-status">GPIO ' + d.gpio + ' · ' + (d.state?'ON':'OFF') + '</div></div>'
            ).join('');
        }
        
        async function toggle(id) {
            const dev = devices.find(d => d.id === id);
            if (!dev) return;
            dev.state = !dev.state;
            render();
            try {
                await fetch(API + '/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: 'Cambia estado de ' + dev.name + ' a ' + (dev.state?'encendido':'apagado')})
                });
            } catch(e) {}
        }
        
        function saveRules() { alert('Reglas guardadas'); }
        function addTimer() { alert('Agregar temporizador'); }
        render();
        </script>"""
        
        html = self.BASE_TEMPLATE.format(title=title, content=content, scripts=scripts)
        path = self.output_dir / "iot.html"
        path.write_text(html)
        return str(path)
