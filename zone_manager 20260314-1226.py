import os
import streamlit as st
import xml.etree.ElementTree as ET
import json
import math
import pandas as pd
import uuid
from datetime import datetime
from shapely.geometry import Point, Polygon

# --- FORCER LE THEME CLAIR NATIVEMENT ---
def setup_light_theme():
    try:
        st_dir = ".streamlit"
        os.makedirs(st_dir, exist_ok=True)
        config_path = os.path.join(st_dir, "config.toml")
        
        theme_config = '[theme]\nbase="light"\nprimaryColor="#6366f1"\n'
        
        if not os.path.exists(config_path):
            with open(config_path, "w") as f:
                f.write(theme_config)
        else:
            with open(config_path, "r") as f:
                content = f.read()
            if 'base="light"' not in content:
                with open(config_path, "w") as f:
                    f.write(theme_config + "\n" + content)
    except:
        pass

setup_light_theme()

# --- CONFIGURATION ---
st.set_page_config(
    page_title="LG Precision Forge | VCP Workspace",
    page_icon="🗞️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PALETTE DE COULEURS ---
VCP_PALETTE = ["#6366f1", "#10b981", "#f43f5e", "#f59e0b", "#06b6d4", "#8b5cf6", "#f97316", "#84cc16"]

def get_zone_color(idx):
    return VCP_PALETTE[idx % len(VCP_PALETTE)]

# --- DESIGN SYSTEM & OPTIMISATION UI ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
    
    footer {visibility: hidden;} 
    
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 0rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 100% !important;
    }
    
    html, body, [class*="css"] { 
        font-family: 'Inter', sans-serif; 
    }
    
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
    
    .vcp-header {
        background: var(--secondary-background-color); 
        color: var(--text-color);
        padding: 1.25rem 2rem; 
        border-radius: 16px;
        border-left: 6px solid var(--primary-color, #6366f1); 
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    
    .warning-card {
        background: rgba(249, 115, 22, 0.1); 
        border: 1px solid rgba(249, 115, 22, 0.2); 
        padding: 1rem; border-radius: 12px; color: #ea580c; font-weight: 600;
        margin-bottom: 1rem;
    }
    
    .leaflet-popup-content {
        font-family: 'Inter', sans-serif !important;
        font-size: 11px !important;
        color: #1e293b !important;
    }
    
    /* 🔴 LE SECRET EST ICI : On cache la Zone de Texte hors de l'écran sans la désactiver */
    div[data-testid="stTextArea"]:has(textarea[aria-label="STREAMLIT_BRIDGE"]) {
        position: absolute !important;
        left: -9999px !important;
        top: -9999px !important;
        width: 0px !important;
        height: 0px !important;
        opacity: 0 !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- UTILS GÉO ---
def mercator_to_latlng(x, y):
    lng = (x / 20037508.34) * 180
    lat = (y / 20037508.34) * 180
    lat = (180 / math.pi) * (2 * math.atan(math.exp((lat * math.pi) / 180)) - math.pi / 2)
    return lat, lng

def latlng_to_mercator(lat, lng):
    x = (lng * 20037508.34) / 180
    y = math.log(math.tan(math.pi / 4 + (lat * math.pi) / 360))
    y = (y * 20037508.34) / math.pi
    return x, y

def format_ilot_name(zone_name):
    name = str(zone_name).strip()
    if len(name) == 4:
        return name + "A"
    return name[:5]

def get_shapely_polygon(polygon_str):
    try:
        parts = [float(p) for p in polygon_str.split(';') if p]
        coords = [mercator_to_latlng(parts[i], parts[i+1]) for i in range(0, len(parts), 2)]
        return Polygon(coords)
    except (ValueError, IndexError):
        return None

# --- SESSION STATE ---
if 'zones' not in st.session_state: st.session_state.zones = []
if 'clients_df' not in st.session_state: st.session_state.clients_df = None
if 'search_query' not in st.session_state: st.session_state.search_query = ""

# --- PARSEURS ZONES ---
def handle_xml(content):
    try:
        root = ET.fromstring(content)
        new_zones = []
        for z in root.findall('.//zone'):
            z_id = f"xml-{uuid.uuid4().hex[:8]}"
            new_zones.append({
                "id": z_id,
                "name": z.find('name').text if z.find('name') is not None else "Zone",
                "startdepot": z.find('startdepot').text if z.find('startdepot') is not None else "33",
                "polygon": z.find('polygon').text if z.find('polygon') is not None else "",
            })
            st.session_state[f"chk_{z_id}"] = True 
        st.session_state.zones.extend(new_zones)
    except ET.ParseError: st.error("Le fichier XML est mal formé.")
    except Exception as e: st.error(f"Erreur XML: {e}")

def handle_json(content):
    try:
        data = json.loads(content)
        raw_zones = data[0].get('zones', []) if isinstance(data, list) else data.get('zones', [])
        new_zones = []
        for z in raw_zones:
            z_id = f"json-{uuid.uuid4().hex[:8]}"
            coords = z.get('polygon', {}).get('geometry', {}).get('coordinates', [[]])[0]
            merc_list = [f"{latlng_to_mercator(lat, lng)[0]:.6f};{latlng_to_mercator(lat, lng)[1]:.6f}" for lng, lat in coords]
            new_zones.append({
                "id": z_id,
                "name": z.get('name', 'Zone JSON'),
                "startdepot": "33",
                "polygon": ";".join(merc_list),
            })
            st.session_state[f"chk_{z_id}"] = True
        st.session_state.zones.extend(new_zones)
    except json.JSONDecodeError: st.error("Le fichier JSON est invalide.")
    except Exception as e: st.error(f"Erreur JSON: {e}")

def run_zoning_algorithm(df):
    df = df.copy() 
    
    for col in ['latitude', 'longitude']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce')

    zone_polygons = []
    for z in st.session_state.zones:
        poly = get_shapely_polygon(z['polygon'])
        if poly: zone_polygons.append({"poly": poly, "name": z['name']})
    
    def process_client(row):
        try:
            p = Point(float(row['latitude']), float(row['longitude']))
            for zp in zone_polygons:
                if zp['poly'].contains(p): 
                    return format_ilot_name(zp['name']), "Validé"
        except (ValueError, IndexError): pass
        statut = "Validé" if pd.notna(row['Ilôt']) and str(row['Ilôt']).strip() != "" else "À corriger"
        return row['Ilôt'], statut

    progress_bar = st.progress(0, text="Mise à jour des affectations...")
    results = []
    chunk_size = 100
    for i in range(0, len(df), chunk_size):
        chunk = df.iloc[i:i+chunk_size]
        results.extend(chunk.apply(process_client, axis=1))
        progress_bar.progress(min((i + chunk_size) / len(df), 1.0), text=f"Calcul : {min(i + chunk_size, len(df))}/{len(df)} clients")
    progress_bar.empty()

    df['Ilôt'] = [r[0] for r in results]
    df['Statut_Forge'] = [r[1] for r in results]
    return df

# --- MOTEUR DE CARTE ---
def render_forge_map(selected_zones, clients_df=None, focus_point=None):
    zones_js = []
    all_coords = []
    unselected_zones_js = [] 
    
    for z in st.session_state.zones:
        raw = [float(p) for p in z['polygon'].split(';') if p]
        pts = [list(mercator_to_latlng(raw[i], raw[i+1])) for i in range(0, len(raw), 2)]
        
        if z in selected_zones:
            idx = st.session_state.zones.index(z)
            zones_js.append({"name": z['name'], "coords": pts, "color": get_zone_color(idx)})
            all_coords.extend(pts)
        else:
            unselected_zones_js.append({"id": z['id'], "name": z['name'], "coords": pts})

    clients_js = []
    if clients_df is not None:
        df_clean = clients_df.dropna(subset=['latitude', 'longitude']).copy()
        for col in ['latitude', 'longitude']:
            df_clean[col] = pd.to_numeric(df_clean[col].astype(str).str.replace(',', '.'), errors='coerce')
        df_clean = df_clean.dropna(subset=['latitude', 'longitude'])
        df_clean = df_clean[(df_clean['latitude'].abs() > 0.001) & (df_clean['longitude'].abs() > 0.001)]
        df_clean = df_clean.fillna('')
        clients_js = df_clean.to_dict('records')
        if not selected_zones:
            for _, row in df_clean.iterrows():
                all_coords.append([float(row['latitude']), float(row['longitude'])])

    center = [44.837789, -0.57918]
    if focus_point:
        center = focus_point
    elif all_coords:
        center = [sum(p[0] for p in all_coords)/len(all_coords), sum(p[1] for p in all_coords)/len(all_coords)]

    map_html = f"""
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/@geoman-io/leaflet-geoman-free@latest/dist/leaflet-geoman.css" />
    <script src="https://unpkg.com/@geoman-io/leaflet-geoman-free@latest/dist/leaflet-geoman.min.js"></script>
    
    <style>
        html, body {{ margin: 0; padding: 0; height: 100%; overflow: hidden; }}
        
        .leaflet-container.leaflet-touch-drag,
        .leaflet-container.leaflet-grab {{ cursor: default !important; }}
        .leaflet-container.leaflet-touch-drag.leaflet-dragging,
        .leaflet-container.leaflet-grab.leaflet-dragging {{ cursor: grabbing !important; }}
        .leaflet-interactive {{ cursor: pointer !important; }}
    </style>
    <div id="map" style="height: 100vh; width: 100%; border-radius: 16px; box-shadow: inset 0 0 0 1px #e2e8f0;"></div>
    <script>
        var map = L.map('map', {{ doubleClickZoom: false }}).setView({center}, {18 if focus_point else 12});
        
        var tileUrl = 'https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png';
        L.tileLayer(tileUrl).addTo(map);
        
        map.pm.setGlobalOptions({{
            snappable: true, snapDistance: 20, allowSelfIntersection: false,
            hintlineStyle: {{ color: '#6366f1', dashArray: '5,5' }}, templineStyle: {{ color: '#6366f1' }}
        }});

        map.pm.addControls({{
            position: 'topleft',
            drawMarker: false, drawCircleMarker: false, drawPolyline: false,
            drawRectangle: false, drawCircle: false, drawText: false,
            editMode: true, dragMode: true, cutPolygon: false,
            removalMode: true, rotateMode: false,
        }});

        var zones = {json.dumps(zones_js)};
        var unselectedZones = {json.dumps(unselected_zones_js)};
        var clients = {json.dumps(clients_js)};
        var focus = {json.dumps(focus_point)};
        var bounds = L.latLngBounds();
        
        var clientMarkers = []; 
        var drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);

        zones.forEach(function(z) {{
            var poly = L.polygon(z.coords, {{color: z.color, fillOpacity: 0.2, weight: 2}});
            poly.bindTooltip(z.name);
            poly.customName = z.name;
            drawnItems.addLayer(poly);
            z.coords.forEach(p => bounds.extend(p));
        }});

        clients.forEach(function(c) {{
            var isFocus = focus && focus[0] == c.latitude && focus[1] == c.longitude;
            var popupHTML = "<div style='max-height:250px; overflow-y:auto; min-width:250px;'><table style='width:100%; border-collapse: collapse;'><thead><tr><th colspan='2' style='background:#f1f5f9; padding:6px; border-radius:4px; text-align:left; border-bottom:2px solid #e2e8f0; color:#1e293b;'>DONNÉES CLIENT</th></tr></thead><tbody>";
            for (var key in c) {{
                if (key !== 'latitude' && key !== 'longitude' && c[key] !== null && c[key] !== '') {{
                    popupHTML += "<tr style='border-bottom: 1px solid #f1f5f9;'><td style='padding:4px; font-weight:700; color:#64748b; vertical-align:top; white-space:nowrap;'>" + key + "</td><td style='padding:4px; color:#1e293b;'>" + c[key] + "</td></tr>";
                }}
            }}
            popupHTML += "</tbody></table></div>";

            var dotColor = (c['Statut_Forge'] === 'À corriger') ? '#f97316' : '#6366f1';
            if (isFocus) dotColor = '#ef4444';

            var marker = L.circleMarker([c.latitude, c.longitude], {{
                radius: isFocus ? 10 : 6, color: isFocus ? 'white' : '#1e293b', 
                fillColor: dotColor, fillOpacity: 0.9, weight: isFocus ? 3 : 1.5,
                pmIgnore: true, snapIgnore: true 
            }}).addTo(map).bindPopup(popupHTML);
            
            marker.isFocus = isFocus;
            marker.on('click', function(e) {{ map.panTo(e.latlng); }});
            clientMarkers.push(marker);
            
            if (!focus && zones.length === 0) bounds.extend([c.latitude, c.longitude]);
        }});

        var infoControl = L.Control.extend({{
            options: {{ position: 'bottomleft' }},
            onAdd: function (map) {{
                this._div = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
                this._div.style.cssText = 'background:white; padding:10px; border-radius:8px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.1); font-family:Inter,sans-serif; color:#1e293b;';
                this.update(0, clients.length);
                return this._div;
            }},
            update: function (count, total) {{
                this._div.innerHTML = '<div style="font-size:10px; text-transform:uppercase; letter-spacing:0.05em; color:#64748b; font-weight:700;">Clients Couverts</div><div style="font-size:18px; font-weight:800; color:#1e293b; line-height:1.2;">' + count + ' <span style="font-size:13px; color:#94a3b8; font-weight:500;">/ ' + total + '</span></div>';
            }}
        }});
        var infoBox = new infoControl();
        map.addControl(infoBox);

        function isInside(latlng, poly) {{
            var polyPoints = poly.getLatLngs ? poly.getLatLngs() : poly;
            var vs = polyPoints;
            while (vs.length > 0 && Array.isArray(vs[0])) {{
                if (typeof vs[0][0] === 'number') break;
                vs = vs[0];
            }}
            var x = latlng.lat, y = latlng.lng;
            var inside = false;
            for (var i = 0, j = vs.length - 1; i < vs.length; j = i++) {{
                var xi = vs[i].lat !== undefined ? vs[i].lat : vs[i][0];
                var yi = vs[i].lng !== undefined ? vs[i].lng : vs[i][1];
                var xj = vs[j].lat !== undefined ? vs[j].lat : vs[j][0];
                var yj = vs[j].lng !== undefined ? vs[j].lng : vs[j][1];
                var intersect = ((yi > y) != (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
                if (intersect) inside = !inside;
            }}
            return inside;
        }}

        function isNearOrInside(latlng, polyCoords, tolerancePx) {{
            if (isInside(latlng, polyCoords)) return true;

            var vs = polyCoords.getLatLngs ? polyCoords.getLatLngs() : polyCoords;
            while (vs.length > 0 && Array.isArray(vs[0])) {{
                if (typeof vs[0][0] === 'number') break;
                vs = vs[0];
            }}

            var bounds = L.latLngBounds();
            for(var k=0; k<vs.length; k++){{
                var latK = vs[k].lat !== undefined ? vs[k].lat : vs[k][0];
                var lngK = vs[k].lng !== undefined ? vs[k].lng : vs[k][1];
                bounds.extend([latK, lngK]);
            }}
            if (!bounds.pad(0.05).contains(latlng)) return false;

            var p = map.latLngToContainerPoint(latlng);
            for (var i = 0, j = vs.length - 1; i < vs.length; j = i++) {{
                var latI = vs[i].lat !== undefined ? vs[i].lat : vs[i][0];
                var lngI = vs[i].lng !== undefined ? vs[i].lng : vs[i][1];
                var latJ = vs[j].lat !== undefined ? vs[j].lat : vs[j][0];
                var lngJ = vs[j].lng !== undefined ? vs[j].lng : vs[j][1];

                var p1 = map.latLngToContainerPoint(L.latLng(latI, lngI));
                var p2 = map.latLngToContainerPoint(L.latLng(latJ, lngJ));

                var l2 = (p1.x - p2.x)*(p1.x - p2.x) + (p1.y - p2.y)*(p1.y - p2.y);
                var dist;
                if (l2 === 0) {{
                    dist = p.distanceTo(p1);
                }} else {{
                    var t = ((p.x - p1.x) * (p2.x - p1.x) + (p.y - p1.y) * (p2.y - p1.y)) / l2;
                    t = Math.max(0, Math.min(1, t));
                    var proj = L.point(p1.x + t * (p2.x - p1.x), p1.y + t * (p2.y - p1.y));
                    dist = p.distanceTo(proj);
                }}

                if (dist <= tolerancePx) return true;
            }}
            return false;
        }}

        function showPulse(latlng) {{
            var circle = L.circleMarker(latlng, {{
                radius: 10, color: '#10b981', fillColor: '#10b981',
                fillOpacity: 0.6, weight: 2, pmIgnore: true
            }}).addTo(map);
            
            var opacity = 0.6;
            var anim = setInterval(function() {{
                opacity -= 0.05;
                circle.setStyle({{ fillOpacity: Math.max(0, opacity), opacity: Math.max(0, opacity * 2) }});
                circle.setRadius(circle.getRadius() + 2);
                if (opacity <= 0) {{
                    clearInterval(anim);
                    map.removeLayer(circle);
                }}
            }}, 30);
        }}

        // --- PONT TECHNIQUE BLINDÉ AVEC TEXTAREA ---
        function sendToPython(payload) {{
            try {{
                var parentDoc = window.parent.document;
                // On vise le textarea caché
                var inputNode = parentDoc.querySelector('textarea[aria-label="STREAMLIT_BRIDGE"]');
                
                if (inputNode) {{
                    // 1. Prendre le focus pour simuler l'utilisateur
                    inputNode.focus();
                    
                    // 2. Injecter la donnée JSON sans alerter React tout de suite
                    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
                    nativeInputValueSetter.call(inputNode, JSON.stringify(payload));
                    
                    // 3. Prévenir React qu'une saisie a eu lieu
                    inputNode.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    
                    // 4. LE SECRET : Faire perdre le focus (blur) au champ. 
                    // Streamlit valide TOUJOURS un textarea lors du blur !
                    inputNode.blur();
                    
                    return true;
                }} else {{
                    console.error("Erreur critique : Le canal Streamlit (textarea) est introuvable.");
                }}
            }} catch(e) {{ console.error("Erreur de transfert JS vers Python :", e); }}
            return false;
        }}

        var lastClickTime = 0;
        var lastClickPos = null;

        map.on('mousedown', function(e) {{
            var now = Date.now();
            var timeDiff = now - lastClickTime;
            
            var isSamePlace = lastClickPos && (e.layerPoint.distanceTo(lastClickPos) < 25);
            
            if (timeDiff < 400 && isSamePlace) {{
                handleMagicDoubleClick(e.latlng);
                lastClickTime = 0; 
            }} else {{
                lastClickTime = now;
                lastClickPos = e.layerPoint;
            }}
        }});

        function handleMagicDoubleClick(latlng) {{
            showPulse(latlng);
            
            var tolerance = 40; 
            var clickedVisible = false;
            
            drawnItems.eachLayer(function(layer) {{
                if ((layer instanceof L.Polygon || layer instanceof L.Rectangle) && isInside(latlng, layer)) {{
                    clickedVisible = true;
                }}
            }});

            if (clickedVisible) {{
                L.popup().setLatLng(latlng)
                    .setContent("<div style='font-size:11px; font-family:Inter; font-weight:600; color:#10b981;'>Ce secteur est déjà affiché.</div>")
                    .openOn(map);
                setTimeout(() => {{ map.closePopup(); }}, 1500);
                return;
            }}

            var found = false;
            for (var i = 0; i < unselectedZones.length; i++) {{
                if (isNearOrInside(latlng, unselectedZones[i].coords, tolerance)) {{
                    found = true;
                    
                    L.popup().setLatLng(latlng)
                        .setContent("<div style='font-size:12px; font-family:Inter; font-weight:700; color:#6366f1;'>⏳ Ouverture de <b>" + unselectedZones[i].name + "</b>...</div>")
                        .openOn(map);
                    
                    sendToPython({{ action: "activate", zone_id: unselectedZones[i].id, zone_name: unselectedZones[i].name, ts: Date.now() }});
                    break;
                }}
            }}
            
            if (!found) {{
                L.popup().setLatLng(latlng)
                    .setContent("<div style='font-size:11px; font-family:Inter; font-weight:600; color:#64748b;'>Aucun secteur masqué à cet endroit.</div>")
                    .openOn(map);
                setTimeout(() => {{ map.closePopup(); }}, 1500);
            }}
        }}

        function updateVisualStatus() {{
            var polygons = [];
            drawnItems.eachLayer(function(layer) {{
                if(layer instanceof L.Polygon || layer instanceof L.Rectangle) polygons.push(layer);
            }});
            var coveredCount = 0;
            clientMarkers.forEach(function(marker) {{
                var inside = false;
                for(var i=0; i<polygons.length; i++) {{
                    if(isInside(marker.getLatLng(), polygons[i])) {{ inside = true; break; }}
                }}
                if(inside) coveredCount++;
                var newColor = inside ? '#6366f1' : '#f97316';
                if(marker.isFocus) newColor = '#ef4444'; 
                marker.setStyle({{fillColor: newColor}});
            }});
            infoBox.update(coveredCount, clientMarkers.length);
        }}

        map.on('pm:create', function (e) {{
            var layer = e.layer;
            layer.customName = "Nouvelle Zone";
            drawnItems.addLayer(layer);
            layer.on('pm:edit', updateVisualStatus);
            layer.on('pm:dragend', updateVisualStatus);
            layer.on('pm:markerdragend', updateVisualStatus);
            updateVisualStatus(); 
        }});

        drawnItems.eachLayer(function(layer) {{
            layer.on('pm:edit', updateVisualStatus);
            layer.on('pm:dragend', updateVisualStatus);
            layer.on('pm:markerdragend', updateVisualStatus);
        }});
        
        map.on('pm:remove', function(e) {{
            drawnItems.removeLayer(e.layer);
            updateVisualStatus();
        }});

        var autoSaveControl = L.Control.extend({{
            options: {{ position: 'topright' }},
            onAdd: function (map) {{
                var container = L.DomUtil.create('div', 'leaflet-control');
                container.style.cursor = 'pointer';
                container.innerHTML = '<div style="background:#10b981; color:white; padding:10px 16px; border-radius:8px; font-weight:800; font-family:Inter,sans-serif; font-size:14px; box-shadow:0 4px 6px rgba(0,0,0,0.2); display:flex; align-items:center; gap:8px; transition:all 0.2s;">💾 Enregistrer et Recalculer</div>';
                
                container.onclick = function(e){{
                    e.preventDefault();
                    var outZones = [];
                    drawnItems.eachLayer(function(layer){{
                        outZones.push({{ name: layer.customName || "Zone", polygon: layer.toGeoJSON() }});
                    }});
                    
                    if (sendToPython({{ action: "save", zones: outZones, ts: Date.now() }})) {{
                        container.innerHTML = '<div style="background:#059669; color:white; padding:10px 16px; border-radius:8px; font-weight:800; font-family:Inter,sans-serif; font-size:14px; box-shadow:0 4px 6px rgba(0,0,0,0.2); display:flex; align-items:center; gap:8px;">✅ Validé !</div>';
                        setTimeout(() => {{ 
                            container.innerHTML = '<div style="background:#10b981; color:white; padding:10px 16px; border-radius:8px; font-weight:800; font-family:Inter,sans-serif; font-size:14px; box-shadow:0 4px 6px rgba(0,0,0,0.2); display:flex; align-items:center; gap:8px;">💾 Enregistrer et Recalculer</div>';
                        }}, 2000);
                    }}
                }}
                return container;
            }}
        }});
        map.addControl(new autoSaveControl());

        if (!focus && (zones.length > 0 || clients.length > 0)) map.fitBounds(bounds, {{padding: [40, 40]}});
        updateVisualStatus(); 
    </script>
    """
    st.components.v1.html(map_html, height=850)

def main():
    
    # --- LE PONT DE COMMUNICATION INFAILLIBLE ---
    # Remplacement par un text_area. Quand il perd le focus (blur), l'info passe à 100% à Streamlit
    bridge_val = st.text_area("STREAMLIT_BRIDGE", key="bridge", label_visibility="collapsed")
    
    if bridge_val and bridge_val != st.session_state.get('last_bridge_val', ''):
        st.session_state['last_bridge_val'] = bridge_val
        try:
            payload = json.loads(bridge_val)
            
            # Action 1 : Sauvegarde
            if payload.get("action") == "save":
                st.session_state.zones = []
                handle_json(json.dumps({"zones": payload.get("zones")}))
                if st.session_state.clients_df is not None:
                    st.session_state.clients_df = run_zoning_algorithm(st.session_state.clients_df)
                st.toast("✅ Frontières enregistrées et Clients recalculés !", icon="💾")
                st.rerun()
                
            # Action 2 : Activation au double clic
            elif payload.get("action") == "activate":
                zone_id = payload.get("zone_id")
                zone_name = payload.get("zone_name", "voisine")
                zone_key = f"chk_{zone_id}"
                
                st.session_state[zone_key] = True
                st.session_state["search_query"] = "" # Vide la recherche pour que la zone s'affiche dans la liste
                
                st.toast(f"✅ Secteur {zone_name} affiché sur la carte !", icon="🗺️")
                st.rerun()
                
        except Exception as e:
            pass

    with st.sidebar:
        st.image("https://www.lg-presse.fr/gallery/logo%20LG%20Presse.jpg?ts=1771514472", width=75)
        st.markdown("### 🗺️ LG Precision Forge")
        
        with st.expander("1️⃣ Importation Secteurs", expanded=not st.session_state.zones):
            files = st.file_uploader("Fichiers XML/JSON", accept_multiple_files=True)
            if st.button("Charger Secteurs", use_container_width=True):
                for f in files:
                    content = f.read().decode("utf-8")
                    if f.name.endswith('.json'): handle_json(content)
                    else: handle_xml(content)
                st.rerun()

        with st.expander("2️⃣ Importation Clients", expanded=(bool(st.session_state.zones) and st.session_state.clients_df is None)):
            csv_file = st.file_uploader("Fichier CSV (Jade)", type=['csv'])
            if csv_file and st.button("Traiter les Clients", use_container_width=True):
                try:
                    df = pd.read_csv(csv_file, sep=None, engine='python') 
                except Exception as e:
                    st.error(f"Erreur lecture CSV: {e}")
                    return
                
                df = run_zoning_algorithm(df)
                st.session_state.clients_df = df
                st.success("Traitement terminé !")
                st.rerun()

        st.divider()

        show_only_anomalies = False
        if st.session_state.clients_df is not None:
            st.markdown("### 🛠️ Outils & Exportation")
            show_only_anomalies = st.checkbox("🚨 Ne montrer que les anomalies", value=False, help="Masque les clients déjà validés pour se concentrer sur les corrections.")
            
            st.caption("Téléchargez votre CSV avec les Ilôts assignés.")
            export_df = st.session_state.clients_df.drop(columns=['Statut_Forge'])
            csv_data = export_df.to_csv(index=False, sep=';').encode('utf-8-sig')
            st.download_button("📥 Télécharger CSV", csv_data, "campagne_forge_ok.csv", "text/csv", use_container_width=True, type="primary")
            st.divider()

        if st.session_state.zones:
            st.markdown("### 📋 Secteurs")
            
            def clear_search():
                st.session_state.search_query = ""
                
            st.markdown("**🔍 Rechercher un secteur...**")
            c_search, c_clear = st.columns([5, 1])
            with c_search:
                st.text_input("Recherche", placeholder="Ex: LB03...", key="search_query", label_visibility="collapsed")
            with c_clear:
                st.button("❌", on_click=clear_search, help="Effacer la recherche", use_container_width=True)
            
            query = st.session_state.search_query
            filtered_zones = [z for z in st.session_state.zones if query.lower() in z['name'].lower()]
            
            st.caption(f"💡 Double-cliquez sur la carte pour révéler un secteur masqué. ({len(filtered_zones)}/{len(st.session_state.zones)} affichés)")
            
            c_all, c_none = st.columns(2)
            if c_all.button("Cocher filtrés", use_container_width=True):
                for z in filtered_zones: st.session_state[f"chk_{z['id']}"] = True
                st.rerun()
            if c_none.button("Décocher filtrés", use_container_width=True):
                for z in filtered_zones: st.session_state[f"chk_{z['id']}"] = False
                st.rerun()
            
            with st.container(height=400):
                sorted_zones = sorted(filtered_zones, key=lambda x: x['name'])
                for z in sorted_zones:
                    st.checkbox(f"{z['name']}", key=f"chk_{z['id']}")

    # --- MAIN UI ---
    if not st.session_state.zones and st.session_state.clients_df is None:
        st.markdown('<h1 style="font-weight:900; font-size:3.5rem; color: #1e293b;">LG Precision <span style="color:#6366f1">Forge</span></h1>', unsafe_allow_html=True)
        st.info("Importez vos secteurs (JSON/XML) puis vos clients (CSV) dans le menu de gauche.")
    else:
        selected_zones = [z for z in st.session_state.zones if st.session_state.get(f"chk_{z['id']}", False)]
        
        st.markdown(f"""
            <div class="vcp-header">
                <h2 style="margin:0; font-weight: 800; letter-spacing: -0.02em; color: #1e293b;">Visualisation Terrain</h2>
                <p style="margin:0; color: #64748b;"><b>{len(selected_zones)} zones</b> | <b>{len(st.session_state.clients_df) if st.session_state.clients_df is not None else 0} clients</b> chargés.</p>
            </div>
        """, unsafe_allow_html=True)

        focus_point = None
        if st.session_state.clients_df is not None:
            unassigned = st.session_state.clients_df[st.session_state.clients_df['Statut_Forge'] == "À corriger"]
            
            if len(unassigned) > 0:
                st.markdown(f"""
                    <div class="warning-card" style="margin-bottom: 1rem;">
                        ⚠️ <b>{len(unassigned)} clients</b> sont situés hors des zones sélectionnées ou n'ont pas d'affectation.
                    </div>
                """, unsafe_allow_html=True)
                
                with st.expander("🛠️ Expertise et Correction Manuelle", expanded=True):
                    st.info("💡 **Ajustement Frontière :** Éditez les polygones sur la carte, puis cliquez sur le bouton vert **💾 Enregistrer et Recalculer** sur la carte.")
                    st.caption("Sélectionnez une ligne ci-dessous pour forcer un client.")
                    
                    zone_names = [format_ilot_name(z['name']) for z in st.session_state.zones]
                    
                    editor_params = {
                        "data": unassigned[['Identité', 'adresse', 'ville', 'Ilôt', 'latitude', 'longitude']],
                        "column_config": {
                            "Ilôt": st.column_config.SelectboxColumn("Affectation Ilôt", options=zone_names, required=True),
                            "latitude": st.column_config.NumberColumn(disabled=True),
                            "longitude": st.column_config.NumberColumn(disabled=True),
                        },
                        "disabled": ["Identité", "adresse", "ville", "latitude", "longitude"],
                        "hide_index": True,
                        "use_container_width": True,
                        "key": "expertise_editor"
                    }
                    
                    try:
                        st.data_editor(**editor_params, selection_mode="single-row")
                    except TypeError:
                        st.data_editor(**editor_params)

                    selection = st.session_state.get("expertise_editor", {}).get("selection", {}).get("rows", [])
                    if selection:
                        sel_idx = selection[0]
                        row = unassigned.iloc[sel_idx]
                        focus_point = [float(row['latitude']), float(row['longitude'])]

                    if st.session_state.get("expertise_editor"):
                        for idx, changes in st.session_state["expertise_editor"]["edited_rows"].items():
                            if "Ilôt" in changes:
                                real_idx = unassigned.index[idx]
                                st.session_state.clients_df.at[real_idx, "Ilôt"] = changes["Ilôt"]
                                st.session_state.clients_df.at[real_idx, "Statut_Forge"] = "Validé (Manuel)"
            else:
                st.success("✅ Tous les clients sont correctement affectés aux zones.")

        map_df = st.session_state.clients_df
        if show_only_anomalies and map_df is not None:
            map_df = map_df[map_df['Statut_Forge'] == "À corriger"]

        render_forge_map(selected_zones, map_df, focus_point=focus_point)

        # --- STATS SUMMARY ---
        if st.session_state.clients_df is not None and selected_zones:
            st.divider()
            st.markdown("### 📊 Statistiques par Secteur Sélectionné")
            
            zone_ilot_names = [format_ilot_name(z['name']) for z in selected_zones]
            filtered_df = st.session_state.clients_df[st.session_state.clients_df['Ilôt'].isin(zone_ilot_names)]
            client_counts = filtered_df['Ilôt'].value_counts()

            num_cols = min(len(selected_zones), 4)
            if num_cols > 0:
                cols = st.columns(num_cols)
                sorted_selected_zones = sorted(selected_zones, key=lambda z: z['name'])
                
                for i, zone in enumerate(sorted_selected_zones):
                    with cols[i % num_cols]:
                        zone_ilot_name = format_ilot_name(zone['name'])
                        count = client_counts.get(zone_ilot_name, 0)
                        st.metric(label=zone['name'], value=f"{count} clients")

if __name__ == "__main__":
    main()