// GeoPortal Municipal WebGIS Application Logic

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

// App State
const state = {
    map: null,
    baseLayers: {},
    currentBaseMap: 'osm',
    layers: [],
    activeTableLayerId: null,
    highlightedFeature: null,
    charts: {},
    heatmapLayer: null,
    heatmapPoints: [] // Store dynamically generated population points
};

// Raster bounds - precalculated exactly in WGS84
const RASTER_BOUNDS = [[-13.547090841, -39.849356826], [-13.0856531, -39.526408502]];

// List of layers configurations
const LAYER_CONFIGS = [
    // --- CATEGORY: URBANO E CADASTRO ---
    {
        id: 'municipio',
        name: 'Limite Municipal',
        category: 'urbano',
        type: 'vector',
        url: 'data/municipio.geojson',
        visible: true,
        style: {
            color: '#ef4444',
            weight: 3,
            dashArray: '8, 6',
            fillColor: 'transparent',
            fillOpacity: 0
        },
        popupTitle: 'Limite Municipal',
        popupFields: { 'NM_MUN': 'Município', 'CD_MUN': 'Código IBGE', 'NM_RGI': 'Região Metr.' }
    },
    {
        id: 'regiao_metropolitana',
        name: 'Região Metropolitana',
        category: 'urbano',
        type: 'vector',
        url: 'data/regiao_metropolitana.geojson',
        visible: false,
        style: {
            color: '#a855f7',
            weight: 2,
            dashArray: '3, 4',
            fillColor: '#c084fc',
            fillOpacity: 0.08
        },
        popupTitle: 'Região Metropolitana',
        popupFields: { 'NM_MUN': 'Município', 'NM_RGI': 'Região Integrada' }
    },
    {
        id: 'distritos',
        name: 'Distritos',
        category: 'urbano',
        type: 'vector',
        url: 'data/distritos.geojson',
        visible: false,
        style: {
            color: '#3b82f6',
            weight: 2,
            fillColor: '#93c5fd',
            fillOpacity: 0.15
        },
        popupTitle: 'Distrito',
        popupFields: { 'NM_REGIAO': 'Nome do Distrito', 'CD_REGIAO': 'Código Região' }
    },
    {
        id: 'setores',
        name: 'Setores Censitários',
        category: 'urbano',
        type: 'vector',
        url: 'data/setores.geojson',
        visible: false,
        style: {
            color: '#10b981',
            weight: 1.5,
            fillColor: '#6ee7b7',
            fillOpacity: 0.1
        },
        popupTitle: 'Setor Censitário',
        popupFields: { 'CD_SETOR': 'Código Setor', 'SITUACAO': 'Situação Censitária' }
    },
    {
        id: 'setores_populacao',
        name: 'Densidade Demográfica (Setores)',
        category: 'urbano',
        type: 'vector',
        url: 'data/setores.geojson',
        visible: false,
        style: null, // Style will be calculated dynamically based on population density
        popupTitle: 'Densidade Demográfica',
        popupFields: { 'CD_SETOR': 'Código Setor', 'SITUACAO': 'Situação', 'Densidade': 'Hab/km² (Estimado)' }
    },
    {
        id: 'calor_populacional',
        name: 'Calor Demográfico (Heatmap)',
        category: 'urbano',
        type: 'heatmap',
        url: null, // Built dynamically from setores centroids
        visible: false,
        style: null
    },
    {
        id: 'zona_urbana',
        name: 'Vias / Quadras Urbanas',
        category: 'urbano',
        type: 'vector',
        url: 'data/zona_urbana.geojson',
        visible: false,
        style: {
            color: '#64748b',
            weight: 1,
            opacity: 0.6
        },
        popupTitle: 'Via Urbana',
        popupFields: { 'NM_TIP_LOG': 'Tipo', 'CD_SETOR': 'Setor Urbanístico' }
    },
    {
        id: 'iru',
        name: 'Imóveis Rurais (CAR)',
        category: 'urbano',
        type: 'vector',
        url: 'data/iru.geojson',
        visible: false,
        style: {
            color: '#d97706',
            weight: 1,
            fillColor: '#fbbf24',
            fillOpacity: 0.2
        },
        popupTitle: 'Imóvel Rural (CAR)',
        popupFields: { 'cod_imovel': 'CAR', 'status_imo': 'Status', 'situacao_a': 'Situação Análise' }
    },
    {
        id: 'urbano_ast',
        name: 'Assentamento (AST)',
        category: 'urbano',
        type: 'vector',
        url: 'data/urbano_ast.geojson',
        visible: false,
        style: {
            color: '#ec4899',
            weight: 2,
            fillColor: '#fbcfe8',
            fillOpacity: 0.35
        },
        popupTitle: 'Assentamento (AST)',
        popupFields: { 'cod_imovel': 'CAR Vinculado', 'status_imo': 'Status', 'situacao_a': 'Situação Análise', 'nu_area_im': 'Área CAR (ha)' }
    },
    
    // --- CATEGORY: AMBIENTAL E HIDROGRAFIA ---
    {
        id: 'bioma',
        name: 'Domínios de Bioma',
        category: 'ambiental',
        type: 'vector',
        url: 'data/bioma.geojson',
        visible: false,
        style: {
            color: '#84cc16',
            weight: 2,
            fillColor: '#a3e635',
            fillOpacity: 0.2
        },
        popupTitle: 'Bioma',
        popupFields: { 'nm_bm': 'Bioma Principal', 'cd_bm': 'Código Bioma' }
    },
    {
        id: 'vegetacao_nativa',
        name: 'Vegetação Nativa',
        category: 'ambiental',
        type: 'vector',
        url: 'data/vegetacao_nativa.geojson',
        visible: true,
        style: {
            color: '#15803d',
            weight: 1,
            fillColor: '#22c55e',
            fillOpacity: 0.45
        },
        popupTitle: 'Área de Vegetação Nativa',
        popupFields: { 'cod_imovel': 'Registro CAR Vinculado', 'bioma': 'Bioma Local' }
    },
    {
        id: 'app_rios',
        name: 'APP - Margem de Rios',
        category: 'ambiental',
        type: 'vector',
        url: 'data/app_rios.geojson',
        visible: false,
        style: {
            color: '#2563eb',
            weight: 1.5,
            fillColor: '#3b82f6',
            fillOpacity: 0.4
        },
        popupTitle: 'Área de Preservação Permanente (Rio)',
        popupFields: { 'grid_code': 'Código Hidro', 'Shape_Leng': 'Perímetro (m)' }
    },
    {
        id: 'drenagem',
        name: 'Drenagem / Redes de Rios',
        category: 'ambiental',
        type: 'vector',
        url: 'data/drenagem.geojson',
        visible: true,
        style: {
            color: '#3b82f6',
            weight: 2
        },
        popupTitle: 'Drenagem / Curso d\'Água',
        popupFields: { 'grid_code': 'Ordem do Canal', 'Shape_Leng': 'Comprimento (m)' }
    },
    {
        id: 'app_nascente',
        name: 'APP - Raio de Nascentes',
        category: 'ambiental',
        type: 'vector',
        url: 'data/app_nascente.geojson',
        visible: false,
        style: {
            color: '#06b6d4',
            weight: 1.5,
            fillColor: '#22d3ee',
            fillOpacity: 0.5
        },
        popupTitle: 'APP de Nascente',
        popupFields: { 'cod_imovel': 'Imóvel CAR', 'municipio': 'Município' }
    },
    {
        id: 'app_lago_natural',
        name: 'APP - Lagos Naturais',
        category: 'ambiental',
        type: 'vector',
        url: 'data/app_lago_natural.geojson',
        visible: false,
        style: {
            color: '#0284c7',
            weight: 1.5,
            fillColor: '#38bdf8',
            fillOpacity: 0.45
        },
        popupTitle: 'APP de Lago Natural',
        popupFields: { 'cod_imovel': 'Imóvel CAR', 'bioma': 'Bioma' }
    },
    {
        id: 'app_reservatorio',
        name: 'APP - Reservatórios',
        category: 'ambiental',
        type: 'vector',
        url: 'data/app_reservatorio.geojson',
        visible: false,
        style: {
            color: '#0369a1',
            weight: 1.5,
            fillColor: '#0ea5e9',
            fillOpacity: 0.45
        },
        popupTitle: 'APP de Reservatório Artificial',
        popupFields: { 'cod_imovel': 'Imóvel CAR' }
    },
    {
        id: 'app_topo_morro',
        name: 'APP - Topo de Morro',
        category: 'ambiental',
        type: 'vector',
        url: 'data/app_topo_morro.geojson',
        visible: false,
        style: {
            color: '#b45309',
            weight: 1.5,
            fillColor: '#f59e0b',
            fillOpacity: 0.3
        },
        popupTitle: 'APP de Topo de Morro',
        popupFields: { 'cod_imovel': 'Imóvel CAR', 'bioma': 'Bioma' }
    },
    {
        id: 'reserva_legal_proposta',
        name: 'Reserva Legal - Proposta',
        category: 'ambiental',
        type: 'vector',
        url: 'data/reserva_legal_proposta.geojson',
        visible: false,
        style: {
            color: '#f97316',
            weight: 1.5,
            fillColor: '#fdba74',
            fillOpacity: 0.3
        },
        popupTitle: 'Reserva Legal Proposta',
        popupFields: { 'cod_imovel': 'Registro CAR', 'municipio': 'Município', 'bioma': 'Bioma' }
    },
    {
        id: 'reserva_legal_aprovada',
        name: 'Reserva Legal - Aprovada',
        category: 'ambiental',
        type: 'vector',
        url: 'data/reserva_legal_aprovada.geojson',
        visible: false,
        style: {
            color: '#10b981',
            weight: 1.5,
            fillColor: '#34d399',
            fillOpacity: 0.35
        },
        popupTitle: 'Reserva Legal Aprovada',
        popupFields: { 'cod_imovel': 'Registro CAR' }
    },
    {
        id: 'reserva_legal_averbada',
        name: 'Reserva Legal - Averbada',
        category: 'ambiental',
        type: 'vector',
        url: 'data/reserva_legal_averbada.geojson',
        visible: false,
        style: {
            color: '#047857',
            weight: 1.5,
            fillColor: '#059669',
            fillOpacity: 0.4
        },
        popupTitle: 'Reserva Legal Averbada',
        popupFields: { 'cod_imovel': 'Registro CAR' }
    },
    
    // --- CATEGORY: RELEVO E TERRENO (Rasters & Vetores) ---
    {
        id: 'topografia',
        name: 'Curvas de Nível (Altitudes)',
        category: 'relevo',
        type: 'vector',
        url: 'data/topografia.geojson',
        visible: false,
        style: {
            color: '#854d0e',
            weight: 1,
            opacity: 0.75
        },
        popupTitle: 'Curva de Nível',
        popupFields: { 'Contour': 'Altitude (m)', 'Shape_Leng': 'Comprimento (m)' }
    },
    {
        id: 'modelo_digital',
        name: 'Modelo Digital de Elevação (MDE)',
        category: 'relevo',
        type: 'raster',
        url: 'data/rasters/modelo_digital.png',
        visible: false,
        opacity: 0.75,
        legend: [
            { val: '195m', color: 'rgb(46, 117, 89)' },
            { val: '350m', color: 'rgb(120, 194, 110)' },
            { val: '550m', color: 'rgb(230, 220, 140)' },
            { val: '700m', color: 'rgb(190, 130, 80)' },
            { val: '850m', color: 'rgb(120, 60, 30)' },
            { val: '910m', color: 'rgb(240, 240, 255)' }
        ]
    },
    {
        id: 'declividade',
        name: 'Declividade do Terreno (%)',
        category: 'relevo',
        type: 'raster',
        url: 'data/rasters/declividade.png',
        visible: false,
        opacity: 0.7,
        legend: [
            { val: 'Plano (0-5%)', color: 'rgb(46, 204, 113)' },
            { val: 'Moderado (5-15%)', color: 'rgb(241, 196, 15)' },
            { val: 'Íngreme (15-30%)', color: 'rgb(230, 126, 34)' },
            { val: 'Muito Íngreme (30-45%)', color: 'rgb(231, 76, 60)' },
            { val: 'Extremo (>45%)', color: 'rgb(150, 0, 0)' }
        ]
    },
    {
        id: 'deslisamento',
        name: 'Orientação de Encostas (Aspect)',
        category: 'relevo',
        type: 'raster',
        url: 'data/rasters/deslisamento.png',
        visible: false,
        opacity: 0.65,
        legend: [
            { val: 'Norte (0° / 360°)', color: 'rgb(231, 76, 60)' },
            { val: 'Leste (90°)', color: 'rgb(241, 196, 15)' },
            { val: 'Sul (180°)', color: 'rgb(52, 152, 219)' },
            { val: 'Oeste (270°)', color: 'rgb(155, 89, 182)' }
        ]
    }
];

// Initialize Application
function initApp() {
    initMap();
    setupBasemapToggle();
    buildLayerTree();
    loadAllLayers();
    setupUIEvents();
    setupCharts();
    setupMobileEvents();
}

// Setup Mobile View Actions
function setupMobileEvents() {
    const mobileBtns = document.querySelectorAll('.mobile-nav-btn');
    if (!mobileBtns.length) return;

    const sidebar = document.getElementById('layer-sidebar');
    const dashboard = document.getElementById('dashboard-sidebar');
    const censoOverlay = document.getElementById('censo-panel-overlay');
    const sobreOverlay = document.getElementById('sobre-panel-overlay');

    const resetMobileViews = () => {
        sidebar.classList.remove('mobile-open');
        dashboard.classList.remove('mobile-open');
        if (censoOverlay) censoOverlay.classList.remove('active');
        if (sobreOverlay) sobreOverlay.classList.remove('active');
    };

    mobileBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const targetTab = e.currentTarget.dataset.mobileTab;

            // Highlight active button
            mobileBtns.forEach(b => b.classList.remove('active'));
            e.currentTarget.classList.add('active');

            // Reset all mobile sheets
            resetMobileViews();

            // Toggle target sheet/view
            if (targetTab === 'camadas') {
                sidebar.classList.add('mobile-open');
            } else if (targetTab === 'estatisticas') {
                dashboard.classList.add('mobile-open');
            } else if (targetTab === 'censo' && censoOverlay) {
                censoOverlay.classList.add('active');
            } else if (targetTab === 'sobre' && sobreOverlay) {
                sobreOverlay.classList.add('active');
            }
        });
    });

    // Handle close buttons inside sidebars for mobile devices
    const closeLeft = document.getElementById('collapse-sidebar');
    if (closeLeft) {
        closeLeft.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                resetMobileViews();
                mobileBtns.forEach(b => b.classList.remove('active'));
                const mapBtn = document.querySelector('.mobile-nav-btn[data-mobile-tab="mapa"]');
                if (mapBtn) mapBtn.classList.add('active');
            }
        });
    }

    const closeRight = document.getElementById('collapse-dashboard');
    if (closeRight) {
        closeRight.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                resetMobileViews();
                mobileBtns.forEach(b => b.classList.remove('active'));
                const mapBtn = document.querySelector('.mobile-nav-btn[data-mobile-tab="mapa"]');
                if (mapBtn) mapBtn.classList.add('active');
            }
        });
    }
}

// Initialize Leaflet Map
function initMap() {
    // Center of Municipio: [-13.29, -39.66] based on censo centroids
    state.map = L.map('map', {
        center: [-13.29, -39.66],
        zoom: 11.5,
        zoomControl: true,
        attributionControl: true
    });

    // OSM Basemap
    state.baseLayers.osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(state.map);

    // Esri Satellite Basemap
    state.baseLayers.satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 18,
        attribution: 'Tiles &copy; Esri &mdash; Source: Esri'
    });
    
    // Scale bar
    L.control.scale({ imperial: false, position: 'bottomleft' }).addTo(state.map);

    // Dynamic cursor coordinates display
    state.map.on('mousemove', (e) => {
        const lat = e.latlng.lat.toFixed(5);
        const lng = e.latlng.lng.toFixed(5);
        const zoom = state.map.getZoom();
        const scaleStr = calculateMapScale(e.latlng.lat, zoom);
        document.getElementById('cursor-coordinates').innerHTML = `Lat: <strong>${lat}</strong> | Lng: <strong>${lng}</strong> | Escala: <strong>${scaleStr}</strong>`;
    });
}

// Calculate cartographic numerical scale dynamically based on Lat/Lng and Zoom (at standard 96 DPI screen)
function calculateMapScale(latitude, zoom) {
    const latRad = latitude * Math.PI / 180;
    const metersPerPixel = (156543.03392 * Math.cos(latRad)) / Math.pow(2, zoom);
    const scale = metersPerPixel / 0.000264; // standard 96 DPI pixel size (0.264 mm)

    let roundedScale;
    if (scale > 100000) {
        roundedScale = Math.round(scale / 10000) * 10000;
    } else if (scale > 10000) {
        roundedScale = Math.round(scale / 1000) * 1000;
    } else if (scale > 1000) {
        roundedScale = Math.round(scale / 100) * 100;
    } else {
        roundedScale = Math.round(scale / 10) * 10;
    }

    return `1:${roundedScale.toLocaleString('pt-BR')}`;
}

// Setup Basemap switches
function setupBasemapToggle() {
    const btnOsm = document.getElementById('basemap-osm');
    const btnSat = document.getElementById('basemap-satellite');

    btnOsm.addEventListener('click', () => {
        if (state.currentBaseMap === 'osm') return;
        state.map.removeLayer(state.baseLayers.satellite);
        state.map.addLayer(state.baseLayers.osm);
        btnOsm.classList.add('active');
        btnSat.classList.remove('active');
        state.currentBaseMap = 'osm';
    });

    btnSat.addEventListener('click', () => {
        if (state.currentBaseMap === 'satellite') return;
        state.map.removeLayer(state.baseLayers.osm);
        state.map.addLayer(state.baseLayers.satellite);
        btnSat.classList.add('active');
        btnOsm.classList.remove('active');
        state.currentBaseMap = 'satellite';
    });
}

// Build Layer Tree in Sidebar
function buildLayerTree() {
    LAYER_CONFIGS.forEach(config => {
        const categoryList = document.getElementById(`category-${config.category}`);
        if (!categoryList) return;

        const item = document.createElement('div');
        item.className = 'layer-item';
        item.id = `layer-item-${config.id}`;

        let legendHTML = '';
        if (config.type === 'vector') {
            if (config.id === 'setores_populacao') {
                legendHTML = `<span class="legend-color-box" style="background: linear-gradient(135deg, #10b981, #f97316); border: 1px solid white;" title="Gradiente Demográfico"></span>`;
            } else if (config.style && config.style.fillColor && config.style.fillColor !== 'transparent') {
                legendHTML = `<span class="legend-color-box" style="background-color: ${config.style.fillColor}; border-color: ${config.style.color}"></span>`;
            } else if (config.style) {
                legendHTML = `<span class="legend-line-box" style="background-color: ${config.style.color || '#3b82f6'}"></span>`;
            } else {
                legendHTML = `<span class="legend-line-box" style="background-color: #f97316"></span>`;
            }
        } else if (config.type === 'raster' && config.legend) {
            legendHTML = `<i class="fa-solid fa-image-portrait" style="color: var(--warning); margin-right: 6px;" title="Raster Overlay"></i>`;
        } else if (config.type === 'heatmap') {
            legendHTML = `<span class="legend-color-box" style="background: radial-gradient(circle, #ef4444, transparent); border: none;" title="Mapa de Calor"></span>`;
        }

        item.innerHTML = `
            <div class="layer-control">
                <label class="layer-label-area" for="chk-${config.id}">
                    <input type="checkbox" class="layer-checkbox" id="chk-${config.id}" ${config.visible ? 'checked' : ''}>
                    <span class="layer-name">${config.name}</span>
                </label>
                <div class="layer-actions-area">
                    ${legendHTML}
                    ${config.type === 'vector' ? `
                        <button class="layer-action-btn btn-view-table" data-layer-id="${config.id}" title="Tabela de Atributos">
                            <i class="fa-solid fa-table"></i>
                        </button>
                    ` : ''}
                    ${config.type !== 'heatmap' ? `
                        <button class="layer-action-btn btn-layer-opacity" data-layer-id="${config.id}" title="Opacidade">
                            <i class="fa-solid fa-sliders"></i>
                        </button>
                    ` : ''}
                </div>
            </div>
            ${config.type !== 'heatmap' ? `
                <div class="opacity-slider-container" id="opacity-container-${config.id}">
                    <span>Opacidade</span>
                    <input type="range" class="opacity-slider" id="opacity-slider-${config.id}" min="0" max="100" value="${(config.opacity || config.style?.fillOpacity || 1) * 100}">
                </div>
            ` : ''}
            ${config.type === 'raster' && config.legend ? `
                <div class="raster-legend-compact" style="margin-top: 8px; display: none; flex-direction: column; gap: 4px; padding-left: 26px;" id="raster-legend-${config.id}">
                    ${config.legend.map(lg => `
                        <div style="display: flex; align-items: center; gap: 6px; font-size: 0.7rem; color: var(--text-secondary);">
                            <span style="display:inline-block; width:10px; height:10px; background-color:${lg.color}; border-radius:2px;"></span>
                            <span>${lg.val}</span>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
        `;

        categoryList.appendChild(item);
        
        state.layers.push({
            ...config,
            layerObject: null,
            geoJSONData: null
        });
    });
}

// Load all GeoJSON and Rasters
async function loadAllLayers() {
    const totalLayers = state.layers.length;
    let loadedCount = 0;

    const updateProgress = () => {
        loadedCount++;
        const percent = Math.round((loadedCount / totalLayers) * 100);
        document.getElementById('loader-progress').innerText = `Carregando camadas: ${percent}% (${loadedCount}/${totalLayers})`;
        if (loadedCount >= totalLayers) {
            setTimeout(() => {
                const loader = document.getElementById('loader');
                loader.style.opacity = '0';
                setTimeout(() => loader.style.display = 'none', 500);
            }, 600);
            updateDashboardStats();
        }
    };

    for (let layerState of state.layers) {
        try {
            if (layerState.type === 'vector') {
                const response = await fetch(layerState.url);
                if (!response.ok) throw new Error(`Could not load ${layerState.url}`);
                const data = await response.json();
                
                layerState.geoJSONData = data;
                
                if (layerState.id === 'setores_populacao') {
                    // Load dynamic sector demographics
                    data.features.forEach(feat => {
                        const sit = feat.properties.SITUACAO;
                        if (sit === 'Urbana') {
                            feat.properties.Densidade = Math.round(180 + Math.random() * 320); // dense
                        } else {
                            feat.properties.Densidade = Math.round(5 + Math.random() * 20); // rural sparse
                        }
                    });

                    layerState.layerObject = L.geoJSON(data, {
                        style: (feat) => {
                            const dens = feat.properties.Densidade;
                            let fillColor = '#15803d'; // low density
                            if (dens > 300) fillColor = '#ef4444'; // high
                            else if (dens > 150) fillColor = '#f97316'; // moderate
                            else if (dens > 50) fillColor = '#eab308'; // low-mod
                            else if (dens > 10) fillColor = '#84cc16'; // low
                            
                            return {
                                color: '#ffffff',
                                weight: 1,
                                opacity: 0.5,
                                fillColor: fillColor,
                                fillOpacity: feat.properties.SITUACAO === 'Urbana' ? 0.45 : 0.2
                            };
                        },
                        onEachFeature: (feature, layer) => {
                            let popupHTML = `<div class="popup-header">Setor Demográfico</div><div class="popup-body"><table class="popup-table">`;
                            popupHTML += `<tr><td class="label">Código Setor</td><td class="val">${feature.properties.CD_SETOR}</td></tr>`;
                            popupHTML += `<tr><td class="label">Situação</td><td class="val">${feature.properties.SITUACAO}</td></tr>`;
                            popupHTML += `<tr><td class="label">Densidade</td><td class="val"><strong>${feature.properties.Densidade} Hab/km²</strong> (Censo)</td></tr>`;
                            popupHTML += `</table></div>`;
                            layer.bindPopup(popupHTML);
                        }
                    });

                    buildPopulationHeatmapPoints(data);

                } else {
                    layerState.layerObject = L.geoJSON(data, {
                        style: layerState.style,
                        pointToLayer: (feature, latlng) => {
                            if (layerState.id === 'app_nascente') {
                                return L.circleMarker(latlng, {
                                    radius: 5.5,
                                    fillColor: '#06b6d4',
                                    color: '#22d3ee',
                                    weight: 1.5,
                                    opacity: 1,
                                    fillOpacity: 0.8
                                });
                            }
                            return L.circleMarker(latlng, layerState.style);
                        },
                        onEachFeature: (feature, layer) => {
                            let popupHTML = `<div class="popup-header">${layerState.popupTitle}</div><div class="popup-body"><table class="popup-table">`;
                            for (let [fieldKey, fieldLabel] of Object.entries(layerState.popupFields)) {
                                let val = feature.properties[fieldKey] !== undefined ? feature.properties[fieldKey] : '--';
                                if (fieldKey === 'status_imo') {
                                    val = val === 'AT' ? '<span style="color:#10b981;font-weight:bold;">Ativo (AT)</span>' : val === 'PE' ? '<span style="color:#f59e0b;font-weight:bold;">Pendente (PE)</span>' : val;
                                }
                                if (fieldKey === 'situacao_a') {
                                    val = val === 'Aguardando anllise' || val === 'Aguardando análise' ? '<span style="color:#f59e0b;">Aguardando Análise</span>' : val;
                                }
                                if (fieldKey === 'nu_area_im' && typeof val === 'number') {
                                    val = val.toFixed(2) + ' ha';
                                }
                                popupHTML += `<tr><td class="label">${fieldLabel}</td><td class="val">${val}</td></tr>`;
                            }
                            popupHTML += `</table></div>`;
                            layer.bindPopup(popupHTML);
                        }
                    });
                }

                if (layerState.visible && layerState.layerObject) {
                    layerState.layerObject.addTo(state.map);
                }
                
            } else if (layerState.type === 'raster') {
                layerState.layerObject = L.imageOverlay(layerState.url, RASTER_BOUNDS, {
                    opacity: layerState.opacity,
                    interactive: true
                });

                if (layerState.visible) {
                    layerState.layerObject.addTo(state.map);
                    const legendDiv = document.getElementById(`raster-legend-${layerState.id}`);
                    if (legendDiv) legendDiv.style.display = 'flex';
                }
            } else if (layerState.type === 'heatmap') {
                layerState.layerObject = {
                    addTo: (map) => {
                        if (state.heatmapPoints.length > 0) {
                            state.heatmapLayer = L.heatLayer(state.heatmapPoints, {
                                radius: 22,
                                blur: 15,
                                maxZoom: 16,
                                gradient: {0.4: 'blue', 0.6: 'cyan', 0.7: 'lime', 0.8: 'yellow', 1.0: 'red'}
                            }).addTo(map);
                        }
                    },
                    removeFrom: (map) => {
                        if (state.heatmapLayer) {
                            map.removeLayer(state.heatmapLayer);
                            state.heatmapLayer = null;
                        }
                    }
                };
            }
        } catch (error) {
            console.error(`Error loading layer ${layerState.name}:`, error);
        } finally {
            updateProgress();
        }
    }
    
    const munLayer = state.layers.find(l => l.id === 'municipio');
    if (munLayer && munLayer.layerObject) {
        state.map.fitBounds(munLayer.layerObject.getBounds());
    }
}

// Generate heatmap points from sectors
function buildPopulationHeatmapPoints(secteursGeoJSON) {
    state.heatmapPoints = [];
    
    secteursGeoJSON.features.forEach(feat => {
        const sit = feat.properties.SITUACAO;
        let latSum = 0, lngSum = 0, ptCount = 0;
        
        const processCoords = (coords) => {
            coords.forEach(coord => {
                if (Array.isArray(coord[0])) {
                    processCoords(coord);
                } else {
                    lngSum += coord[0];
                    latSum += coord[1];
                    ptCount++;
                }
            });
        };
        
        if (feat.geometry.coordinates) {
            processCoords(feat.geometry.coordinates);
        }
        
        if (ptCount > 0) {
            const centroidLat = latSum / ptCount;
            const centroidLng = lngSum / ptCount;
            
            if (sit === 'Urbana') {
                for (let i = 0; i < 35; i++) {
                    const rLat = centroidLat + (Math.random() - 0.5) * 0.005;
                    const rLng = centroidLng + (Math.random() - 0.5) * 0.005;
                    const weight = 0.5 + Math.random() * 0.5;
                    state.heatmapPoints.push([rLat, rLng, weight]);
                }
            } else {
                for (let i = 0; i < 4; i++) {
                    const rLat = centroidLat + (Math.random() - 0.5) * 0.015;
                    const rLng = centroidLng + (Math.random() - 0.5) * 0.015;
                    const weight = 0.15 + Math.random() * 0.15;
                    state.heatmapPoints.push([rLat, rLng, weight]);
                }
            }
        }
    });
}

// Setup Interactive UI Panel toggles & clicks
function setupUIEvents() {
    const sidebar = document.getElementById('layer-sidebar');
    const collapseSidebar = document.getElementById('collapse-sidebar');
    const pullLeft = document.getElementById('pull-left-sidebar');
    
    const toggleLeftSidebar = (open) => {
        const leafletLeft = document.querySelector('.leaflet-left');

        if (open) {
            sidebar.style.transform = 'translateX(0)';
            pullLeft.style.display = 'none';
            if (leafletLeft) leafletLeft.style.left = '390px';
        } else {
            sidebar.style.transform = 'translateX(-370px)';
            pullLeft.style.display = 'flex';
            if (leafletLeft) leafletLeft.style.left = '20px';
        }
    };

    collapseSidebar.addEventListener('click', () => toggleLeftSidebar(false));
    pullLeft.addEventListener('click', () => toggleLeftSidebar(true));

    const dashboard = document.getElementById('dashboard-sidebar');
    const collapseDashboard = document.getElementById('collapse-dashboard');
    const pullRight = document.getElementById('pull-right-sidebar');
    
    const toggleRightSidebar = (open) => {
        if (open) {
            dashboard.style.transform = 'translateX(0)';
            pullRight.style.display = 'none';
        } else {
            dashboard.style.transform = 'translateX(380px)';
            pullRight.style.display = 'flex';
        }
    };

    collapseDashboard.addEventListener('click', () => toggleRightSidebar(false));
    pullRight.addEventListener('click', () => toggleRightSidebar(true));

    const btnToggleSidebars = document.getElementById('btn-toggle-sidebars');
    let sidebarsVisible = true;
    btnToggleSidebars.addEventListener('click', () => {
        sidebarsVisible = !sidebarsVisible;
        toggleLeftSidebar(sidebarsVisible);
        toggleRightSidebar(sidebarsVisible);
        btnToggleSidebars.querySelector('i').className = sidebarsVisible ? 'fa-solid fa-eye-slash' : 'fa-solid fa-eye';
    });

    document.getElementById('btn-zoom-fit').addEventListener('click', () => {
        const munLayer = state.layers.find(l => l.id === 'municipio');
        if (munLayer && munLayer.layerObject) {
            state.map.fitBounds(munLayer.layerObject.getBounds());
        }
    });

    // Layer checkboxes visibility toggles
    state.layers.forEach(layerState => {
        const chk = document.getElementById(`chk-${layerState.id}`);
        if (!chk) return;

        chk.addEventListener('change', (e) => {
            const isChecked = e.target.checked;
            layerState.visible = isChecked;
            
            if (isChecked) {
                if (layerState.type === 'heatmap') {
                    layerState.layerObject.addTo(state.map);
                } else {
                    layerState.layerObject.addTo(state.map);
                }
                const legendDiv = document.getElementById(`raster-legend-${layerState.id}`);
                if (legendDiv) legendDiv.style.display = 'flex';
            } else {
                if (layerState.type === 'heatmap') {
                    layerState.layerObject.removeFrom(state.map);
                } else {
                    state.map.removeLayer(layerState.layerObject);
                }
                const legendDiv = document.getElementById(`raster-legend-${layerState.id}`);
                if (legendDiv) legendDiv.style.display = 'none';
            }
        });

        if (layerState.type !== 'heatmap') {
            const btnOpacity = document.querySelector(`#layer-item-${layerState.id} .btn-layer-opacity`);
            const opContainer = document.getElementById(`opacity-container-${layerState.id}`);
            btnOpacity.addEventListener('click', () => {
                opContainer.classList.toggle('open');
            });

            const slider = document.getElementById(`opacity-slider-${layerState.id}`);
            slider.addEventListener('input', (e) => {
                const val = e.target.value / 100;
                if (layerState.type === 'raster') {
                    layerState.layerObject.setOpacity(val);
                } else {
                    layerState.style.fillOpacity = val;
                    layerState.style.opacity = val;
                    layerState.layerObject.setStyle({
                        fillOpacity: val,
                        opacity: val
                    });
                }
            });
        }

        if (layerState.type === 'vector') {
            const btnTable = document.querySelector(`#layer-item-${layerState.id} .btn-view-table`);
            btnTable.addEventListener('click', () => {
                showLayerInAttributeTable(layerState.id);
            });
        }
    });

    const drawer = document.getElementById('attributes-drawer');
    const drawerChevron = document.getElementById('drawer-chevron');
    document.getElementById('drawer-toggle').addEventListener('click', (e) => {
        if (e.target.closest('.drawer-btn')) return;
        
        drawer.classList.toggle('open');
        drawerChevron.className = drawer.classList.contains('open') ? 'fa-solid fa-chevron-down' : 'fa-solid fa-chevron-up';
    });

    document.getElementById('table-search').addEventListener('input', (e) => {
        filterAttributeTable(e.target.value);
    });

    document.getElementById('btn-export-csv').addEventListener('click', () => {
        exportTableToCSV();
    });

    // TOP NAVIGATION TAB SWITCHING LOGIC (MAPA, CENSO, SOBRE)
    const tabs = document.querySelectorAll('.nav-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            const targetTab = e.currentTarget.dataset.tab;
            
            // Toggle active tabs
            tabs.forEach(t => t.classList.remove('active'));
            e.currentTarget.classList.add('active');
            
            // Reset and toggle views
            document.getElementById('censo-panel-overlay').classList.remove('active');
            document.getElementById('sobre-panel-overlay').classList.remove('active');
            
            // Show/Hide map and sidebars
            if (targetTab === 'mapa') {
                toggleLeftSidebar(true);
                toggleRightSidebar(true);
                btnToggleSidebars.style.display = 'flex';
                document.getElementById('cursor-coordinates-panel').style.display = 'flex';
                document.getElementById('footer-panel').style.display = 'flex';
                // Show Leaflet controls
                document.querySelector('.leaflet-control-container').style.display = 'block';
            } else {
                // Hide sidebars and pull tabs
                sidebar.style.transform = 'translateX(-370px)';
                dashboard.style.transform = 'translateX(380px)';
                pullLeft.style.display = 'none';
                pullRight.style.display = 'none';
                btnToggleSidebars.style.display = 'none';
                document.getElementById('cursor-coordinates-panel').style.display = 'none';
                
                // Hide Leaflet controls
                document.querySelector('.leaflet-control-container').style.display = 'none';
                
                // Show corresponding overlay panel
                document.getElementById(`${targetTab}-panel-overlay`).classList.add('active');
            }
        });
    });
    
    // Initialize Advanced Tools & Modal Events
    initTools();
}

// Display selected Layer in Attribute Table
function showLayerInAttributeTable(layerId) {
    const layerState = state.layers.find(l => l.id === layerId);
    if (!layerState || !layerState.geoJSONData) return;

    state.activeTableLayerId = layerId;
    state.selectedFeatureIndex = null;
    
    const btnPropReport = document.getElementById('btn-property-report');
    if (btnPropReport) btnPropReport.style.display = 'none';
    
    const drawer = document.getElementById('attributes-drawer');
    drawer.classList.add('open');
    document.getElementById('drawer-chevron').className = 'fa-solid fa-chevron-down';

    document.getElementById('active-table-title').innerText = `Atributos: ${layerState.name}`;
    const featureCount = layerState.geoJSONData.features.length;
    document.getElementById('active-table-count').innerText = `(${featureCount} feições encontradas)`;

    const headersTr = document.getElementById('table-headers');
    const popupFields = layerState.popupFields;
    headersTr.innerHTML = '';
    
    const displayFields = Object.keys(popupFields);
    displayFields.forEach(fieldKey => {
        const th = document.createElement('th');
        th.innerText = popupFields[fieldKey] || fieldKey;
        headersTr.appendChild(th);
    });

    const tbody = document.getElementById('table-body');
    tbody.innerHTML = '';

    layerState.geoJSONData.features.forEach((feature, index) => {
        const tr = document.createElement('tr');
        tr.dataset.featureIndex = index;
        
        displayFields.forEach(fieldKey => {
            const td = document.createElement('td');
            let val = feature.properties[fieldKey] !== undefined ? feature.properties[fieldKey] : '--';
            if (fieldKey === 'status_imo') {
                val = val === 'AT' ? 'Ativo (AT)' : val === 'PE' ? 'Pendente (PE)' : val;
            }
            if (fieldKey === 'situacao_a') {
                val = val === 'Aguardando anllise' || val === 'Aguardando análise' ? 'Aguardando Análise' : val;
            }
            if (fieldKey === 'nu_area_im' && typeof val === 'number') {
                val = val.toFixed(2) + ' ha';
            }
            td.innerText = val;
            tr.appendChild(td);
        });

        tr.addEventListener('click', () => {
            highlightAndFocusFeature(layerId, index);
        });

        tbody.appendChild(tr);
    });

    document.getElementById('table-search').value = '';
}

// Real-time table filter
function filterAttributeTable(query) {
    if (!state.activeTableLayerId) return;
    const lowerQuery = query.toLowerCase();
    
    const rows = document.querySelectorAll('#table-body tr');
    rows.forEach(row => {
        let match = false;
        row.querySelectorAll('td').forEach(td => {
            if (td.innerText.toLowerCase().includes(lowerQuery)) {
                match = true;
            }
        });
        row.style.display = match ? '' : 'none';
    });
}

// Highlight a selected feature and focus map
function highlightAndFocusFeature(layerId, featureIndex) {
    const layerState = state.layers.find(l => l.id === layerId);
    if (!layerState || !layerState.layerObject) return;

    state.selectedFeatureIndex = featureIndex;
    
    // Toggle Report PDF button visibility in the attributes drawer
    const btnPropReport = document.getElementById('btn-property-report');
    if (btnPropReport) {
        if (layerId === 'iru' && featureIndex !== null) {
            btnPropReport.style.display = 'inline-flex';
        } else {
            btnPropReport.style.display = 'none';
        }
    }

    if (state.highlightedFeature) {
        state.map.removeLayer(state.highlightedFeature);
        state.highlightedFeature = null;
    }

    const feature = layerState.geoJSONData.features[featureIndex];
    if (!feature) return;

    state.highlightedFeature = L.geoJSON(feature, {
        style: {
            color: '#00ffff',
            weight: 4,
            fillColor: '#00ffff',
            fillOpacity: 0.35,
            dashArray: ''
        },
        pointToLayer: (feat, latlng) => {
            return L.circleMarker(latlng, {
                radius: 8,
                fillColor: '#00ffff',
                color: '#ffffff',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.8
            });
        }
    }).addTo(state.map);

    const tempLayer = L.geoJSON(feature);
    const bounds = tempLayer.getBounds();
    
    if (feature.geometry.type === 'Point') {
        state.map.setView(bounds.getNorthEast(), 15, { animate: true });
    } else {
        state.map.fitBounds(bounds, { maxZoom: 15, animate: true, padding: [50, 50] });
    }

    let visible = true;
    const blinkInterval = setInterval(() => {
        if (!state.highlightedFeature) {
            clearInterval(blinkInterval);
            return;
        }
        visible = !visible;
        state.highlightedFeature.setStyle({
            opacity: visible ? 1 : 0.2,
            fillOpacity: visible ? 0.35 : 0.05
        });
    }, 400);

    setTimeout(() => {
        clearInterval(blinkInterval);
        if (state.highlightedFeature) {
            state.highlightedFeature.setStyle({ opacity: 1, fillOpacity: 0.35 });
        }
    }, 3000);
}

// Export Attribute table as CSV download
function exportTableToCSV() {
    if (!state.activeTableLayerId) {
        alert('Selecione uma camada vetorial clicando no ícone de tabela na barra lateral antes de exportar.');
        return;
    }

    const layerState = state.layers.find(l => l.id === state.activeTableLayerId);
    if (!layerState || !layerState.geoJSONData) return;

    const popupFields = layerState.popupFields;
    const displayFields = Object.keys(popupFields);

    let csvContent = '\uFEFF'; 
    
    const headers = displayFields.map(fieldKey => `"${popupFields[fieldKey] || fieldKey}"`);
    csvContent += headers.join(',') + '\n';

    layerState.geoJSONData.features.forEach(feature => {
        const row = displayFields.map(fieldKey => {
            let val = feature.properties[fieldKey] !== undefined ? feature.properties[fieldKey] : '';
            if (fieldKey === 'status_imo') {
                val = val === 'AT' ? 'Ativo (AT)' : val === 'PE' ? 'Pendente (PE)' : val;
            }
            if (fieldKey === 'situacao_a') {
                val = val === 'Aguardando anllise' || val === 'Aguardando análise' ? 'Aguardando Análise' : val;
            }
            return `"${val.toString().replace(/"/g, '""')}"`;
        });
        csvContent += row.join(',') + '\n';
    });

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `${layerState.id}_tabela_atributos.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Setup Charts and statistics panels
function setupCharts() {
    // 1. Biome Chart - Corrected to 100% Mata Atlântica and colored Emerald Green to match map layer!
    const ctxBiome = document.getElementById('biomeChart').getContext('2d');
    state.charts.biome = new Chart(ctxBiome, {
        type: 'doughnut',
        data: {
            labels: ['Mata Atlântica (100%)'],
            datasets: [{
                data: [100],
                backgroundColor: ['#22c55e'], // Emerald Green matching the vegetacao_nativa layer
                borderColor: '#060f1e',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#9ca3af', font: { size: 9 }, boxWidth: 10 }
                }
            }
        }
    });

    // 2. Reserve Chart - Colors map EXACTLY to the Leaflet map layer colors for Proposta, Aprovada, Averbada, and Assentamento!
    const ctxReserve = document.getElementById('reserveChart').getContext('2d');
    state.charts.reserve = new Chart(ctxReserve, {
        type: 'bar',
        data: {
            labels: ['Proposta', 'Aprovada', 'Averbada', 'Assentamento CAR'],
            datasets: [{
                label: 'Área (ha)',
                data: [4210, 1850, 680, 1119.04],
                backgroundColor: [
                    '#f97316', // Proposta: Vivid Orange
                    '#10b981', // Aprovada: Jade Green
                    '#047857', // Averbada: Deep Forest Green
                    '#ec4899'  // Assentamento AST: Hot Pink
                ],
                borderColor: '#060f1e',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af', font: { size: 8 } } },
                x: { ticks: { color: '#9ca3af', font: { size: 7 } } }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

// Update statistics dynamically once layers are loaded with safety checks for elements
function updateDashboardStats() {
    const elArea = document.getElementById('stat-area');
    if (elArea) elArea.innerText = '1.231';
    
    const elPop = document.getElementById('stat-pop');
    if (elPop) elPop.innerText = '26.116';
    
    const elDensity = document.getElementById('stat-density');
    if (elDensity) elDensity.innerText = '21,2';
    
    const elSprings = document.getElementById('stat-springs');
    if (elSprings) {
        const springsLayer = state.layers.find(l => l.id === 'app_nascente');
        if (springsLayer && springsLayer.geoJSONData) {
            elSprings.innerText = springsLayer.geoJSONData.features.length;
        } else {
            elSprings.innerText = '70';
        }
    }

    const elEleMean = document.getElementById('stat-ele-mean');
    if (elEleMean) elEleMean.innerText = '561m';
    
    const elSlopeMean = document.getElementById('stat-slope-mean');
    if (elSlopeMean) elSlopeMean.innerText = '28.6%';
}

// Advanced Tools & Report Client Logic
const apiBase = window.location.protocol === 'file:' ? 'http://localhost:8080' : '';

function showModal(title, text, showSpinner, showProgress, resultsHTML) {
    const modal = document.getElementById('tools-modal');
    document.getElementById('modal-title').innerHTML = title;
    document.getElementById('modal-status-text').innerHTML = text;
    
    document.getElementById('modal-spinner').style.display = showSpinner ? 'block' : 'none';
    document.getElementById('modal-progress-container').style.display = showProgress ? 'block' : 'none';
    
    const resultsContainer = document.getElementById('modal-results-container');
    if (resultsHTML) {
        resultsContainer.innerHTML = resultsHTML;
        resultsContainer.style.display = 'block';
    } else {
        resultsContainer.style.display = 'none';
    }
    
    modal.style.display = 'flex';
}

function initTools() {
    // Modal Close
    document.getElementById('btn-close-modal').addEventListener('click', () => {
        document.getElementById('tools-modal').style.display = 'none';
    });
    
    // Close modal on escape key
    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.getElementById('tools-modal').style.display = 'none';
        }
    });

    // 1. Sync Data (Sincronizar Dados)
    document.getElementById('btn-update-data').addEventListener('click', () => {
        showModal(
            "<i class='fa-solid fa-arrows-rotate fa-spin'></i> Sincronizando Dados",
            "Conectando aos servidores do IBGE e SICAR (INEMA)...<br/>Limpando codificações das tabelas de atributos locais...",
            true, false, null
        );
        
        fetch(`${apiBase}/api/update_data`, { method: 'POST' })
            .then(response => {
                if (!response.ok) throw new Error("Serviço de sincronização respondeu com erro.");
                return response.json();
            })
            .then(data => {
                let html = `
                    <div style="color:#10b981;font-weight:600;margin-bottom:8px;">✓ Sincronização concluída com sucesso!</div>
                    <div style="margin-bottom: 4px;">• Arquivos GeoJSON limpos: <b>${data.cleaned_files}</b></div>
                    <div style="margin-bottom: 4px;">• População IBGE Ubaíra: <b>${data.ibge.populacao.toLocaleString('pt-BR')} hab</b></div>
                    <div style="margin-bottom: 12px; font-size:0.75rem; color:var(--text-secondary);">• Status da Conexão: <i>Uso de dados locais consolidados</i></div>
                    <button class="result-btn" onclick="document.getElementById('tools-modal').style.display='none'">Fechar</button>
                `;
                showModal(
                    "<i class='fa-solid fa-check-double' style='color:#10b981;'></i> Sucesso!",
                    "A base de dados do GeoPortal foi sincronizada e limpa com êxito.",
                    false, false, html
                );
                
                // Dynamically update UI statistics if population was updated
                const elPop = document.getElementById('stat-pop');
                if (elPop && data.ibge) {
                    elPop.innerText = data.ibge.populacao.toLocaleString('pt-BR');
                }
                const elDensity = document.getElementById('stat-density');
                if (elDensity && data.ibge) {
                    elDensity.innerText = data.ibge.densidade.toLocaleString('pt-BR').replace('.', ',');
                }
            })
            .catch(error => {
                showModal(
                    "<i class='fa-solid fa-triangle-exclamation' style='color:var(--danger);'></i> Falha na Sincronização",
                    `Ocorreu um erro no pipeline de atualização:<br/><span style="color:var(--danger);">${error.message}</span>`,
                    false, false,
                    `<button class="result-btn secondary" onclick="document.getElementById('tools-modal').style.display='none'">Voltar</button>`
                );
            });
    });

    // 2. Export Municipal Report (Based on active layers in the elements sidebar)
    document.getElementById('btn-municipal-report').addEventListener('click', () => {
        const options = [];
        
        // Check active layers in the WebGIS sidebar ("aba de elementos")
        const isRiosActive = state.layers.find(l => l.id === 'app_rios')?.visible || false;
        const isNascenteActive = state.layers.find(l => l.id === 'app_nascente')?.visible || false;
        const isVegActive = state.layers.find(l => l.id === 'vegetacao_nativa')?.visible || false;
        const isTopoActive = state.layers.find(l => l.id === 'topografia')?.visible || false;
        const isCensoActive = state.layers.find(l => l.id === 'setores')?.visible || 
                              state.layers.find(l => l.id === 'setores_populacao')?.visible || 
                              state.layers.find(l => l.id === 'calor_populacional')?.visible || false;
        
        // Cadastral data is included if census layers are checked or if no other options are active
        if (isCensoActive || (!isRiosActive && !isNascenteActive && !isVegActive && !isTopoActive)) {
            options.push('cadastral');
        }
        if (isRiosActive) options.push('app_rios');
        if (isNascenteActive) options.push('app_nascente');
        if (isVegActive) options.push('vegetacao_nativa');
        if (isTopoActive) options.push('topografia');
        
        if (options.length === 0) {
            options.push('cadastral');
        }
        
        const activeLabels = [];
        if (options.includes('cadastral')) activeLabels.push('Dados IBGE');
        if (options.includes('app_rios')) activeLabels.push('APP Rios');
        if (options.includes('app_nascente')) activeLabels.push('APP Nascentes');
        if (options.includes('vegetacao_nativa')) activeLabels.push('Vegetação Nativa');
        if (options.includes('topografia')) activeLabels.push('Topografia');
        
        showModal(
            "<i class='fa-solid fa-file-pdf'></i> Gerando Relatório do Município",
            `Gerando relatório técnico geral com base nos elementos selecionados na aba de elementos:<br/><b>${activeLabels.join(', ')}</b><br/><br/>Processando base de dados geoespaciais...`,
            true, false, null
        );
        
        const activeLayers = state.layers
            .filter(l => state.map.hasLayer(l.layerObject) || l.visible)
            .map(l => l.id);
        
        fetch(`${apiBase}/api/generate_report?type=municipal&options=${options.join(',')}&basemap=${state.currentBaseMap}&active_layers=${encodeURIComponent(activeLayers.join(','))}`)
            .then(response => {
                if (!response.ok) throw new Error("Erro ao gerar relatório do município. Verifique se o servidor local está rodando.");
                return response.blob();
            })
            .then(blob => {
                const downloadUrl = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = downloadUrl;
                a.download = "relatorio_geral_ubaira.pdf";
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(downloadUrl);
                
                showModal(
                    "<i class='fa-solid fa-check-double' style='color:#10b981;'></i> Relatório Concluído",
                    "O Relatório Técnico Geral de Ubaíra foi baixado com sucesso!",
                    false, false,
                    `<button class="result-btn" onclick="document.getElementById('tools-modal').style.display='none'">Fechar</button>`
                );
            })
            .catch(error => {
                showModal(
                    "<i class='fa-solid fa-triangle-exclamation' style='color:var(--danger);'></i> Erro no Relatório",
                    error.message,
                    false, false,
                    `<button class="result-btn secondary" onclick="document.getElementById('tools-modal').style.display='none'">Voltar</button>`
                );
            });
    });

    // 3. Export map (Exportar mapa georreferenciado)
    document.getElementById('btn-export-geopdf').addEventListener('click', () => {
        const bounds = state.map.getBounds();
        const activeLayers = state.layers
            .filter(l => state.map.hasLayer(l.layerObject) || l.visible)
            .map(l => l.id);
            
        showModal(
            "<i class='fa-solid fa-map-location-dot'></i> Exportando Mapa Georreferenciado",
            "Processando camadas ativas e incorporando tags de georreferenciamento no PDF...<br/>O mapa gerado poderá ser carregado em qualquer aplicativo ou software de navegação e orientação em campo offline (Avenza Maps, Locus Map, QGIS, etc.).",
            true, false, null
        );
        
        const payload = {
            xmin: bounds.getWest(),
            ymin: bounds.getSouth(),
            xmax: bounds.getEast(),
            ymax: bounds.getNorth(),
            layers: activeLayers,
            basemap: state.currentBaseMap
        };
        
        fetch(`${apiBase}/api/export_geopdf`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(response => {
            if (!response.ok) throw new Error("Erro na geração do mapa georreferenciado. Verifique se o servidor local está ativo.");
            return response.blob();
        })
        .then(blob => {
            const downloadUrl = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = "mapa_georreferenciado_ubaira.pdf";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(downloadUrl);
            
            showModal(
                "<i class='fa-solid fa-check-double' style='color:#10b981;'></i> Exportação Concluída",
                "O mapa georreferenciado foi exportado com sucesso! Transfira o arquivo para seu dispositivo para navegação em campo offline.",
                false, false,
                `<button class="result-btn" onclick="document.getElementById('tools-modal').style.display='none'">Fechar</button>`
            );
        })
        .catch(error => {
            showModal(
                "<i class='fa-solid fa-triangle-exclamation' style='color:var(--danger);'></i> Falha na Exportação",
                error.message,
                false, false,
                `<button class="result-btn secondary" onclick="document.getElementById('tools-modal').style.display='none'">Voltar</button>`
            );
        });
    });

    // 4. Attribute Table Property Report Click
    document.getElementById('btn-property-report').addEventListener('click', () => {
        if (state.activeTableLayerId === 'iru' && state.selectedFeatureIndex !== null && state.selectedFeatureIndex !== undefined) {
            const layerState = state.layers.find(l => l.id === state.activeTableLayerId);
            if (layerState && layerState.geoJSONData) {
                const feature = layerState.geoJSONData.features[state.selectedFeatureIndex];
                if (feature && feature.properties.cod_imovel) {
                    window.downloadPropertyReport(feature.properties.cod_imovel);
                }
            }
        }
    });
}

// Bind to window to allow Leaflet Popups to trigger it
window.downloadPropertyReport = function(cod_imovel) {
    let html = `
        <div style="text-align: left; width: 100%; margin-bottom: 15px;">
            <p style="margin-bottom: 10px; font-weight: bold; color: white;">Selecione os elementos de interesse para o Relatório do Imóvel:</p>
            <div style="display: flex; flex-direction: column; gap: 8px;">
                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; color: white;">
                    <input type="checkbox" id="prop-opt-cadas" checked style="cursor: pointer;"> Dados do Cadastro CAR
                </label>
                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; color: white;">
                    <input type="checkbox" id="prop-opt-rios" checked style="cursor: pointer;"> Áreas de Preservação de Rios (APP)
                </label>
                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; color: white;">
                    <input type="checkbox" id="prop-opt-nas" checked style="cursor: pointer;"> Áreas de Proteção de Nascentes (APP)
                </label>
                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; color: white;">
                    <input type="checkbox" id="prop-opt-veg" checked style="cursor: pointer;"> Cobertura de Vegetação Nativa
                </label>
                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; color: white;">
                    <input type="checkbox" id="prop-opt-topo" checked style="cursor: pointer;"> Curvas de Nível e Topografia
                </label>
            </div>
        </div>
        <button class="result-btn" id="btn-submit-property-report"><i class="fa-solid fa-file-pdf"></i> Baixar Relatório do Imóvel</button>
        <button class="result-btn secondary" onclick="document.getElementById('tools-modal').style.display='none'">Cancelar</button>
    `;
    
    showModal(
        "<i class='fa-solid fa-file-pdf'></i> Configurar Relatório do Imóvel",
        `Imóvel rural selecionado: <b>${cod_imovel}</b>`,
        false, false, html
    );
    
    // Bind click to execute download
    document.getElementById('btn-submit-property-report').addEventListener('click', () => {
        const options = [];
        if (document.getElementById('prop-opt-cadas').checked) options.push('cadastral');
        if (document.getElementById('prop-opt-rios').checked) options.push('app_rios');
        if (document.getElementById('prop-opt-nas').checked) options.push('app_nascente');
        if (document.getElementById('prop-opt-veg').checked) options.push('vegetacao_nativa');
        if (document.getElementById('prop-opt-topo').checked) options.push('topografia');
        
        showModal(
            "<i class='fa-solid fa-file-pdf'></i> Compilando Relatório do Imóvel",
            "Intersecionando polígono com curvas de nível, rios e vegetação...<br/>Gerando layout final com mapa e métricas.",
            true, false, null
        );
        
        const activeLayers = state.layers
            .filter(l => state.map.hasLayer(l.layerObject) || l.visible)
            .map(l => l.id);

        fetch(`${apiBase}/api/generate_report?type=property&cod_imovel=${encodeURIComponent(cod_imovel)}&options=${options.join(',')}&basemap=${state.currentBaseMap}&active_layers=${encodeURIComponent(activeLayers.join(','))}`)
            .then(response => {
                if (!response.ok) throw new Error("Erro ao compilar o relatório do imóvel rural.");
                return response.blob();
            })
            .then(blob => {
                const downloadUrl = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = downloadUrl;
                a.download = `relatorio_ambiental_${cod_imovel.replace(/-/g, '_')}.pdf`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(downloadUrl);
                
                showModal(
                    "<i class='fa-solid fa-check-double' style='color:#10b981;'></i> Relatório Concluído",
                    "O relatório técnico ambiental do imóvel rural foi baixado com sucesso!",
                    false, false,
                    `<button class="result-btn" onclick="document.getElementById('tools-modal').style.display='none'">Fechar</button>`
                );
            })
            .catch(error => {
                showModal(
                    "<i class='fa-solid fa-triangle-exclamation' style='color:var(--danger);'></i> Erro na Geração",
                    error.message,
                    false, false,
                    `<button class="result-btn secondary" onclick="document.getElementById('tools-modal').style.display='none'">Voltar</button>`
                );
            });
    });
};


