import os
import streamlit as st
import xml.etree.ElementTree as ET
import json
import math
import pandas as pd
import uuid
import urllib.request
import urllib.parse
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
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(8px);
        color: #1e293b;
        padding: 0.75rem 1.5rem; 
        border-radius: 12px;
        border-left: 6px solid #6366f1; 
        margin-bottom: 1rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        display: flex;
        flex-direction: row;
        flex-wrap: wrap;
        justify-content: space-between;
        align-items: center;
        gap: 0.5rem;
        position: sticky;
        top: 2.5rem;
        z-index: 999;
    }
    
    /* Pour que le sticky fonctionne dans Streamlit, il faut cibler le conteneur parent natif */
    [data-testid="stElementContainer"]:has(.vcp-header) {
        position: sticky !important;
        top: 2.5rem !important;
        z-index: 999 !important;
    }
    
    @keyframes pulse-warning {
        0% { opacity: 1; }
        50% { opacity: 0.3; }
        100% { opacity: 1; }
    }
    .warning-blink {
        animation: pulse-warning 1.5s infinite ease-in-out;
        color: #ea580c;
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
    # S'assurer que la chaîne fait au moins 5 caractères (comble avec des espaces)
    name = name.ljust(5, ' ')
    res = name[:5]
    
    # Vérifier le 5ème caractère (index 4) et le remplacer si besoin
    if res[4] in ['_', ' ']:
        res = res[:4] + 'A'
        
    return res

def get_shapely_polygon(polygon_str):
    try:
        parts = [float(p) for p in polygon_str.split(';') if p]
        coords = [mercator_to_latlng(parts[i], parts[i+1]) for i in range(0, len(parts), 2)]
        return Polygon(coords)
    except (ValueError, IndexError):
        return None

def geocode_ban(adresse, ville, cp=""):
    query = f"{adresse} {cp} {ville}".strip()
    url = f"https://api-adresse.data.gouv.fr/search/?q={urllib.parse.quote(query)}&limit=1"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data['features']:
                feature = data['features'][0]
                coords = feature['geometry']['coordinates']
                props = feature['properties']
                return coords[1], coords[0], props.get('city', ''), props.get('postcode', ''), props.get('name', '') # lat, lon, ville, cp, adresse
    except Exception:
        pass
    return None, None, None, None, None

# --- SESSION STATE ---
if 'zones' not in st.session_state: st.session_state.zones = []
if 'clients_df' not in st.session_state: st.session_state.clients_df = None
if 'search_query' not in st.session_state: st.session_state.search_query = ""
if 'selected_client_idx' not in st.session_state: st.session_state.selected_client_idx = None

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
                "color": None
            })
            st.session_state[f"state_chk_{z_id}"] = True 
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
                "color": z.get('color', None)
            })
            st.session_state[f"state_chk_{z_id}"] = True
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
            zone_color = z.get('color') or get_zone_color(idx)
            zones_js.append({"id": z['id'], "name": z['name'], "coords": pts, "color": zone_color})
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
        df_clean['df_index'] = df_clean.index
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
        var lightMap = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            maxZoom: 19,
            attribution: '© OpenStreetMap, © CARTO'
        }});
        
        var satelliteMap = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
            maxZoom: 19,
            attribution: 'Tiles © Esri'
        }});

        var map = L.map('map', {{ 
            doubleClickZoom: false,
            layers: [lightMap] // La vue "Plan Clair" reste la vue par défaut au chargement
        }}).setView({center}, {18 if focus_point else 12});
        
        var baseMaps = {{ "Plan Clair": lightMap, "Satellite": satelliteMap }};
        
        L.control.layers(baseMaps, null, {{position: 'topright'}}).addTo(map);
        
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
        var vcpPalette = {json.dumps(VCP_PALETTE)};
        var bounds = L.latLngBounds();
        
        var clientMarkers = []; 
        var drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);

        // --- CRÉATION DE LA PALETTE DE COULEURS ---
        function createColorPopup(layer) {{
            var container = document.createElement('div');
            container.style.textAlign = 'center';
            container.innerHTML = '<div style="font-size:12px; font-weight:bold; margin-bottom:8px; color:#1e293b;">🎨 Couleur du secteur</div>' +
                                  '<div style="display:flex; flex-wrap:wrap; width:120px; justify-content:center; gap:6px;" class="color-palette"></div>';
            var paletteContainer = container.querySelector('.color-palette');
            vcpPalette.forEach(function(c) {{
                var btn = document.createElement('div');
                btn.style.cssText = 'background:' + c + '; width:22px; height:22px; border-radius:50%; cursor:pointer; border: 2px solid white; box-shadow: 0 1px 3px rgba(0,0,0,0.3); transition: transform 0.1s;';
                btn.onmouseover = function() {{ btn.style.transform = 'scale(1.2)'; }};
                btn.onmouseout = function() {{ btn.style.transform = 'scale(1)'; }};
                btn.onclick = function() {{
                    layer.setStyle({{color: c}});
                    layer.options.color = c;
                }};
                paletteContainer.appendChild(btn);
            }});
            return container;
        }}

        zones.forEach(function(z) {{
            var poly = L.polygon(z.coords, {{color: z.color, fillOpacity: 0.2, weight: 2}});
            poly.bindTooltip(z.name);
            poly.customName = z.name;
            poly.customId = z.id;
            poly.bindPopup(createColorPopup(poly));
            drawnItems.addLayer(poly);
            z.coords.forEach(p => bounds.extend(p));
        }});

        clients.forEach(function(c) {{
            var isFocus = focus && focus[0] == c.latitude && focus[1] == c.longitude;
            var btnHtml = "<button onclick='map.setView([" + c.latitude + ", " + c.longitude + "], 18); sendToPython({{action: `client_click`, client_idx: " + JSON.stringify(c.df_index) + ", ts: Date.now()}})' style='padding:4px 8px; background:#6366f1; color:white; border:none; border-radius:4px; font-weight:bold; cursor:pointer; font-size:11px; box-shadow: 0 1px 2px rgba(0,0,0,0.1);'>✏️ Modifier</button>";
            var popupHTML = "<div style='max-height:250px; overflow-y:auto; min-width:250px;'><table style='width:100%; border-collapse: collapse;'><thead><tr><th colspan='2' style='background:#f1f5f9; padding:6px; border-radius:4px; border-bottom:2px solid #e2e8f0; color:#1e293b;'><div style='display:flex; justify-content:space-between; align-items:center;'><span style='font-weight:800;'>DONNÉES CLIENT</span>" + btnHtml + "</div></th></tr></thead><tbody>";
            for (var key in c) {{
                if (key !== 'latitude' && key !== 'longitude' && key !== 'df_index' && c[key] !== null && c[key] !== '') {{
                    var displayValue = c[key];
                    if (key === 'Statut_Forge' && String(displayValue).includes('Manuel')) {{
                        displayValue = "✅ " + displayValue;
                    }}
                    if (key.toLowerCase() === 'adresse') {{
                        displayValue = "<b>" + displayValue + "</b>";
                    }}
                    popupHTML += "<tr style='border-bottom: 1px solid #f1f5f9;'><td style='padding:4px; font-weight:700; color:#64748b; vertical-align:top; white-space:nowrap;'>" + key + "</td><td style='padding:4px; color:#1e293b;'>" + displayValue + "</td></tr>";
                }}
            }}
            popupHTML += "</tbody></table></div>";

            var dotColor;
            if (c['Statut_Forge'] && c['Statut_Forge'].includes('Manuel')) {{
                dotColor = '#10b981'; // Vert pour modification manuelle
            }} else if (c['Statut_Forge'] === 'À corriger') {{
                dotColor = '#f97316'; // Orange pour à corriger
            }} else {{
                dotColor = '#6366f1'; // Bleu classique
            }}
            if (isFocus) dotColor = '#10b981'; // Vert pour le point focus

            var marker = L.circleMarker([c.latitude, c.longitude], {{
                radius: isFocus ? 10 : 6, color: isFocus ? 'white' : '#1e293b', 
                fillColor: dotColor, fillOpacity: 0.9, weight: isFocus ? 3 : 1.5,
                pmIgnore: true, snapIgnore: true, clientStatus: c['Statut_Forge']
            }}).addTo(map).bindPopup(popupHTML);
            
            marker.isFocus = isFocus;
            marker.on('click', function(e) {{ 
                map.setView(e.latlng, 18);
            }});
            clientMarkers.push(marker);
            
            if (!focus && zones.length === 0) bounds.extend([c.latitude, c.longitude]);
        }});

        // Si un point est focus, on ouvre son infobulle
        if (focus) {{
            var focusedMarker = clientMarkers.find(m => m.isFocus);
            if (focusedMarker) {{
                // On attend un court instant pour s'assurer que le centrage de la carte est terminé
                setTimeout(function() {{
                    focusedMarker.openPopup();
                }}, 200);
            }}
        }}

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
                
                var newColor;
                if (!inside) {{
                    newColor = '#f97316'; // À corriger
                }} else if (marker.options.clientStatus && marker.options.clientStatus.includes('Manuel')) {{
                    newColor = '#10b981'; // Vert pour manuel
                }} else {{
                    newColor = '#6366f1'; // Bleu classique
                }}
                
                if(marker.isFocus) newColor = '#10b981'; 
                marker.setStyle({{fillColor: newColor}});
            }});
            infoBox.update(coveredCount, clientMarkers.length);
        }}

        map.on('pm:create', function (e) {{
            var layer = e.layer;
            layer.customName = "Nouvelle Zone";
            layer.options.color = '#6366f1'; // Couleur par défaut
            layer.bindPopup(createColorPopup(layer));
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
                        outZones.push({{ id: layer.customId, name: layer.customName || "Zone", polygon: layer.toGeoJSON(), color: layer.options.color }});
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

@st.dialog("⚠️ Confirmation requise")
def export_confirmation_dialog(export_df, anomalies_mask, anomalies_count):
    st.warning(f"{anomalies_count} lignes en anomalies sont affectées au code ZZ99. L'opérateur doit confirmer ou annuler (oui/non)")
    
    # Application des règles ZZ99 et 'non'
    export_df.loc[anomalies_mask, 'Ilôt'] = 'ZZ99'
    export_df.loc[anomalies_mask, 'Statut Portage'] = 'non'
    export_df = export_df.drop(columns=['Statut_Forge'])
    
    csv_data = export_df.to_csv(index=False, sep=';').encode('utf-8-sig')
    
    c1, c2 = st.columns(2)
    with c1:
        if st.download_button("✅ Oui", csv_data, "campagne_forge_ok.csv", "text/csv", use_container_width=True, type="primary"):
            st.rerun()
    with c2:
        if st.button("❌ Non", use_container_width=True):
            st.rerun()

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
                saved_zones = payload.get("zones", [])
                
                # Identification des zones actuellement affichées sur la carte
                visible_zone_ids = [z['id'] for z in st.session_state.zones if st.session_state.get(f"state_chk_{z['id']}", False)]
                saved_zone_ids = [z.get('id') for z in saved_zones if z.get('id')]
                
                # 1. Supprimer uniquement les zones qui étaient affichées mais qui ont été effacées avec la gomme
                deleted_zone_ids = [z_id for z_id in visible_zone_ids if z_id not in saved_zone_ids]
                st.session_state.zones = [z for z in st.session_state.zones if z['id'] not in deleted_zone_ids]
                
                # 2. Mettre à jour les zones existantes
                updated_zones_dict = {z['id']: z for z in saved_zones if z.get('id')}
                for z in st.session_state.zones:
                    if z['id'] in updated_zones_dict:
                        updated_z = updated_zones_dict[z['id']]
                        z['name'] = updated_z['name']
                        z['color'] = updated_z.get('color', z.get('color'))
                        
                        geom = updated_z['polygon']['geometry']
                        coords = geom['coordinates'][0] if geom['type'] == 'Polygon' else (geom['coordinates'][0][0] if geom['type'] == 'MultiPolygon' else [])
                            
                        if coords:
                            merc_list = [f"{latlng_to_mercator(pt[1], pt[0])[0]:.6f};{latlng_to_mercator(pt[1], pt[0])[1]:.6f}" for pt in coords]
                            z['polygon'] = ";".join(merc_list)
                
                # 3. Ajouter les nouvelles zones dessinées de toutes pièces
                for updated_z in saved_zones:
                    if not updated_z.get('id'):
                        z_id = f"custom-{uuid.uuid4().hex[:8]}"
                        geom = updated_z['polygon']['geometry']
                        coords = geom['coordinates'][0] if geom['type'] == 'Polygon' else (geom['coordinates'][0][0] if geom['type'] == 'MultiPolygon' else [])
                            
                        if coords:
                            merc_list = [f"{latlng_to_mercator(pt[1], pt[0])[0]:.6f};{latlng_to_mercator(pt[1], pt[0])[1]:.6f}" for pt in coords]
                            st.session_state.zones.append({
                                "id": z_id,
                                "name": updated_z['name'],
                                "startdepot": "33",
                                "polygon": ";".join(merc_list),
                                "color": updated_z.get('color')
                            })
                            st.session_state[f"state_chk_{z_id}"] = True
                            st.session_state[f"ui_chk_{z_id}"] = True

                if st.session_state.clients_df is not None:
                    st.session_state.clients_df = run_zoning_algorithm(st.session_state.clients_df)
                st.toast("✅ Frontières enregistrées et Clients recalculés !", icon="💾")
                
            # Action 2 : Activation au double clic
            elif payload.get("action") == "activate":
                zone_id = payload.get("zone_id")
                zone_name = payload.get("zone_name", "voisine")
                
                st.session_state[f"state_chk_{zone_id}"] = True
                st.session_state[f"ui_chk_{zone_id}"] = True
                st.session_state["search_query"] = "" # Vide la recherche pour que la zone s'affiche dans la liste
                
                st.toast(f"✅ Secteur {zone_name} affiché sur la carte !", icon="🗺️")

            # Action 3 : Clic sur un client
            elif payload.get("action") == "client_click":
                st.session_state.selected_client_idx = payload.get("client_idx")
                
        except Exception as e:
            pass

    with st.sidebar:
        st.markdown('<div style="display: flex; justify-content: center; background-color: #eef2ff; padding: 12px; border-radius: 16px; margin-bottom: 10px;"><img src="https://www.lg-presse.fr/gallery/logo%20LG%20Presse.jpg?ts=1771514472" width="75" style="border-radius: 8px; mix-blend-mode: multiply;"></div>', unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center;' title='Importez vos secteurs (JSON/XML) puis vos clients (CSV) dans le menu de gauche.'>🗺️ LG Precision Repérages <span style='cursor: help; color: #94a3b8; font-size: 0.8em;'>❔</span></h3>", unsafe_allow_html=True)
        
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
                    csv_file.seek(0)
                    df = pd.read_csv(csv_file, sep=None, engine='python', encoding='utf-8') 
                except UnicodeDecodeError:
                    # Si le fichier contient des accents au format Windows/Excel (Latin-1)
                    csv_file.seek(0)
                    try:
                        df = pd.read_csv(csv_file, sep=None, engine='python', encoding='latin-1')
                    except Exception as e:
                        st.error(f"Erreur lecture CSV (latin-1): {e}")
                        return
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
            
            export_df = st.session_state.clients_df.copy()
            
            # Identifier les lignes en anomalie (sans Ilôt défini)
            is_missing_ilot = export_df['Ilôt'].isna() | (export_df['Ilôt'].astype(str).str.strip() == '') | (export_df['Ilôt'].astype(str).str.lower() == 'nan')
            is_anomaly = export_df['Statut_Forge'] == "À corriger"
            anomalies_mask = is_missing_ilot & is_anomaly
            
            if anomalies_mask.any():
                anomalies_count = anomalies_mask.sum()
                if st.button("📥 Télécharger CSV", use_container_width=True, type="primary"):
                    export_confirmation_dialog(export_df, anomalies_mask, anomalies_count)
            else:
                # Aucune anomalie, export direct classique
                export_df = export_df.drop(columns=['Statut_Forge'])
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
            if c_all.button("Tout cocher", use_container_width=True):
                for z in filtered_zones: 
                    st.session_state[f"state_chk_{z['id']}"] = True
                    st.session_state[f"ui_chk_{z['id']}"] = True
                st.rerun()
                
            def uncheck_all_zones():
                for z in st.session_state.zones:
                    st.session_state[f"state_chk_{z['id']}"] = False
                    st.session_state[f"ui_chk_{z['id']}"] = False
                st.session_state.search_query = ""
                
            c_none.button("Tout décocher", use_container_width=True, on_click=uncheck_all_zones)
            
            with st.container(height=400):
                sorted_zones = sorted(filtered_zones, key=lambda x: x['name'])
                
                def toggle_zone(z_id):
                    st.session_state[f"state_chk_{z_id}"] = st.session_state[f"ui_chk_{z_id}"]

                for z in sorted_zones:
                    st.checkbox(f"{z['name']}", value=st.session_state.get(f"state_chk_{z['id']}", False), key=f"ui_chk_{z['id']}", on_change=toggle_zone, args=(z['id'],))

    # --- MAIN UI ---
    selected_zones = [z for z in st.session_state.zones if st.session_state.get(f"state_chk_{z['id']}", False)]
    
    warning_html = ""
    if st.session_state.clients_df is not None:
        unassigned_count = len(st.session_state.clients_df[st.session_state.clients_df['Statut_Forge'] == "À corriger"])
        if unassigned_count > 0:
            warning_html = f" <span class='warning-blink'>| ⚠️ <b>{unassigned_count} clients</b> sont situés hors des zones sélectionnées ou n'ont pas d'affectation.</span>"

    st.markdown(f"""
        <div class="vcp-header">
            <h2 style="margin:0; font-size: 1.4rem; font-weight: 800; letter-spacing: -0.02em; color: #1e293b;">Visualisation Terrain</h2>
            <p style="margin:0; color: #64748b; font-size: 0.95rem;"><b>{len(selected_zones)} zones</b> | <b>{len(st.session_state.clients_df) if st.session_state.clients_df is not None else 0} clients</b> chargés.{warning_html}</p>
        </div>
    """, unsafe_allow_html=True)

    focus_point = st.session_state.pop("saved_focus", None)
    if st.session_state.clients_df is not None:
        unassigned = st.session_state.clients_df[st.session_state.clients_df['Statut_Forge'] == "À corriger"]
        
        if len(unassigned) > 0:
            is_editing = st.session_state.get('selected_client_idx') is not None
            with st.expander("🛠️ Expertise et Correction Manuelle", expanded=not is_editing):
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

    # --- BLOC ÉDITION CLIENT ---
    if st.session_state.get('selected_client_idx') is not None:
        idx = st.session_state.selected_client_idx
        if idx in st.session_state.clients_df.index:
            row = st.session_state.clients_df.loc[idx]
            try:
                focus_point = [float(row['latitude']), float(row['longitude'])]
            except:
                pass
            
            with st.expander(f"✏️ Modification du client : {row.get('Identité', 'Inconnu')}", expanded=True):
                with st.form("edit_client_form"):
                    cols = st.columns(4)
                    identite = cols[0].text_input("Identité", value="" if pd.isna(row.get('Identité')) else str(row.get('Identité')))
                    adresse = cols[1].text_input("Adresse", value="" if pd.isna(row.get('adresse')) else str(row.get('adresse')))
                    ville = cols[2].text_input("Ville", value="" if pd.isna(row.get('ville')) else str(row.get('ville')))
                    
                    cp_col = next((c for c in st.session_state.clients_df.columns if str(c).lower() in ['cp', 'code postal', 'code_postal']), None)
                    comp_col = next((c for c in st.session_state.clients_df.columns if 'compl' in str(c).lower()), None)
                    
                    cp = cols[3].text_input("Code Postal", value="" if not cp_col or pd.isna(row[cp_col]) else str(row[cp_col]))
                    if comp_col: complement = st.text_input("Complément", value="" if pd.isna(row[comp_col]) else str(row[comp_col]))
                    else: complement = ""
                        
                    c1, c2, c3, c4 = st.columns([1.4, 1.2, 1.2, 0.8])
                    submitted = c1.form_submit_button("💾 Enregistrer les textes")
                    ban_requested = c2.form_submit_button("🌍 Re-géocoder (BAN)")
                    
                    # Préparation de l'URL pour la recherche exploratoire
                    search_query = f"{adresse} {cp} {ville}".strip()
                    search_query = " ".join(search_query.split()) # Nettoyage des espaces multiples
                    # Le site de la BAN ne supportant pas l'injection par URL, on utilise Google Maps pour l'enquête visuelle
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(search_query)}"
                    c3.link_button("🔍 Explorer sur Maps", maps_url)
                    
                    cancel = c4.form_submit_button("❌ Fermer")
                    
                    if submitted or ban_requested:
                        st.session_state.clients_df.at[idx, 'Identité'] = identite
                        st.session_state.clients_df.at[idx, 'adresse'] = adresse
                        st.session_state.clients_df.at[idx, 'ville'] = ville
                        if cp_col: st.session_state.clients_df.at[idx, cp_col] = cp
                        if comp_col: st.session_state.clients_df.at[idx, comp_col] = complement
                        
                        if ban_requested:
                            lat, lon, new_city, new_cp, new_adresse = geocode_ban(adresse, ville, cp)
                            if lat and lon:
                                st.session_state.clients_df.at[idx, 'latitude'], st.session_state.clients_df.at[idx, 'longitude'] = lat, lon
                                if new_city: st.session_state.clients_df.at[idx, 'ville'] = new_city
                                if cp_col and new_cp: st.session_state.clients_df.at[idx, cp_col] = new_cp
                                if new_adresse: st.session_state.clients_df.at[idx, 'adresse'] = new_adresse
                                
                                temp_df = st.session_state.clients_df.loc[[idx]].copy()
                                temp_df = run_zoning_algorithm(temp_df) # Recalcul de l'ilôt avec la nouvelle coordonnée
                                new_status = temp_df.at[idx, 'Statut_Forge']
                                if new_status == "Validé": 
                                    new_status = "Validé (Manuel)"
                                st.session_state.clients_df.at[idx, 'Ilôt'], st.session_state.clients_df.at[idx, 'Statut_Forge'] = temp_df.at[idx, 'Ilôt'], new_status
                                st.toast("✅ Coordonnées BAN mises à jour !", icon="🌍")
                                st.session_state.saved_focus = [lat, lon]
                                st.rerun()
                            else: st.error("❌ Adresse introuvable dans la Base Adresse Nationale.")
                        else:
                            st.session_state.clients_df.at[idx, "Statut_Forge"] = "Validé (Manuel)"
                            st.toast("✅ Informations enregistrées !", icon="💾")
                            try: st.session_state.saved_focus = [float(st.session_state.clients_df.at[idx, 'latitude']), float(st.session_state.clients_df.at[idx, 'longitude'])]
                            except: pass
                            st.rerun()
                    if cancel: 
                        try: st.session_state.saved_focus = [float(st.session_state.clients_df.at[idx, 'latitude']), float(st.session_state.clients_df.at[idx, 'longitude'])]
                        except: pass
                        st.session_state.selected_client_idx = None; st.rerun()

    map_df = st.session_state.clients_df
    if show_only_anomalies and map_df is not None:
        map_df = map_df[map_df['Statut_Forge'] == "À corriger"]

    render_forge_map(selected_zones, map_df, focus_point=focus_point)

if __name__ == "__main__":
    main()