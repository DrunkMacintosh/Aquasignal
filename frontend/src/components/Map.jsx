// MapLibre GL choropleth with two layer sets sharing one map instance:
//   districts — real province boundaries, area-weighted risk (default view)
//   grid      — the model's native 0.25° cells (detail view)
//   roads     — no choropleth; swaps the satellite basemap for an Esri street
//               basemap so every road and highway reads clearly
// on a keyless satellite basemap (Esri World Imagery + Esri reference labels;
// attribution is a usage requirement and surfaces via the control).
//
// The map object is created exactly once. Data refreshes go through
// getSource().setData() and view switches flip layer visibility — the WebGL
// context, camera, and handlers are never torn down.
import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import {
  fillColorExpression,
  formatCellName,
  formatMonth,
  riskBand,
  trendInfo,
} from '../lib/risk.js';
import { MapSkeleton } from './Skeletons.jsx';

const ESRI_TILE = (service) =>
  `https://server.arcgisonline.com/ArcGIS/rest/services/${service}/MapServer/tile/{z}/{y}/{x}`;
const SATELLITE_STYLE = {
  version: 8,
  sources: {
    'esri-imagery': {
      type: 'raster',
      tiles: [ESRI_TILE('World_Imagery')],
      tileSize: 256,
      maxzoom: 19,
      attribution: 'Imagery © Esri, Maxar, Earthstar Geographics, GIS User Community',
    },
    'esri-reference': {
      type: 'raster',
      tiles: [ESRI_TILE('Reference/World_Boundaries_and_Places')],
      tileSize: 256,
      maxzoom: 19,
      attribution: 'Boundaries &amp; places © Esri',
    },
    'esri-street': {
      type: 'raster',
      tiles: [ESRI_TILE('World_Street_Map')],
      tileSize: 256,
      maxzoom: 19,
      attribution: 'Streets © Esri, HERE, Garmin, OpenStreetMap contributors',
    },
  },
  layers: [
    { id: 'basemap-imagery', type: 'raster', source: 'esri-imagery' },
    // Street basemap for the roads view. Hidden until selected; toggled
    // against the satellite layers in applyViewVisibility(). Sits below the
    // reference anchor so the risk choropleth still renders above it.
    {
      id: 'basemap-street',
      type: 'raster',
      source: 'esri-street',
      layout: { visibility: 'none' },
    },
    // Risk layers are inserted before this one, so place names and admin
    // boundaries stay readable above the choropleth.
    { id: 'basemap-reference', type: 'raster', source: 'esri-reference' },
  ],
};
const ANCHOR_LAYER_ID = 'basemap-reference';
// Satellite basemap layers, hidden as a group when the roads view swaps in the
// street basemap.
const SATELLITE_BASEMAP_LAYERS = ['basemap-imagery', 'basemap-reference'];
const STREET_BASEMAP_LAYER = 'basemap-street';

const EMPTY_COLLECTION = { type: 'FeatureCollection', features: [] };
const MEKONG_DELTA_CENTER = [105.8, 9.8];

const GRID = {
  source: 'risk-cells',
  promoteId: 'cell_id',
  layers: { fill: 'risk-fill', outline: 'risk-outline', selected: 'risk-selected' },
};
const DISTRICTS = {
  source: 'district-risk',
  promoteId: 'district_name',
  layers: {
    fill: 'district-fill',
    outline: 'district-outline',
    selected: 'district-selected',
  },
};

// fill-color (see fillColorExpression): the RISK_RAMP across an absolute 0-100
// domain, so a shade always means the same score. The dense, hue-shifting top
// half (red -> magenta -> violet -> near-black above 75) keeps Vietnam's
// mostly-critical districts visually distinct.
const HOVER_OPACITY = [
  'case',
  ['boolean', ['feature-state', 'hover'], false], 0.92,
  0.62,
];

export default function RiskMap({
  gridData,
  districtData,
  view, // 'districts' | 'grid' | 'roads'
  month,
  selectedCellId,
  selectedDistrict,
  onSelectCell,
  onSelectDistrict,
  isLoading,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const hoveredRef = useRef(null); // { source, id } | null
  const [isReady, setIsReady] = useState(false);
  const [tooltip, setTooltip] = useState(null); // { x, y, kind, props }

  // Mirror reactive props into a ref so the once-registered map handlers
  // always read current values.
  const propsRef = useRef({});
  propsRef.current = { view, onSelectCell, onSelectDistrict };

  const clearHover = () => {
    const map = mapRef.current;
    if (hoveredRef.current && map?.getSource(hoveredRef.current.source)) {
      map.setFeatureState(hoveredRef.current, { hover: false });
    }
    hoveredRef.current = null;
  };

  useEffect(() => {
    if (!containerRef.current) return undefined;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: SATELLITE_STYLE,
      center: MEKONG_DELTA_CENTER,
      zoom: 7,
      minZoom: 4,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');

    map.on('load', () => {
      addRiskLayers(map, GRID, { outlineOpacity: 0.18, outlineWidth: 0.5 });
      addRiskLayers(map, DISTRICTS, { outlineOpacity: 0.5, outlineWidth: 1.25 });
      applyViewVisibility(map, propsRef.current.view);
      setIsReady(true);
    });

    // Hover/click handlers are delegated by layer id; registering them once
    // here survives every data refresh.
    const attach = (config, kind, selectKey) => {
      map.on('mousemove', config.layers.fill, (event) => {
        const feature = event.features?.[0];
        if (!feature) return;
        map.getCanvas().style.cursor = 'pointer';
        if (hoveredRef.current?.id !== feature.id) clearHover();
        hoveredRef.current = { source: config.source, id: feature.id };
        map.setFeatureState(hoveredRef.current, { hover: true });
        setTooltip({ x: event.point.x, y: event.point.y, kind, props: feature.properties });
      });
      map.on('mouseleave', config.layers.fill, () => {
        map.getCanvas().style.cursor = '';
        clearHover();
        setTooltip(null);
      });
      map.on('click', config.layers.fill, (event) => {
        const feature = event.features?.[0];
        if (feature) propsRef.current[selectKey]?.(feature.properties);
      });
    };
    attach(GRID, 'cell', 'onSelectCell');
    attach(DISTRICTS, 'district', 'onSelectDistrict');

    return () => {
      mapRef.current = null;
      map.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Data refreshes swap the GeoJSON in place. Open tooltips are cleared:
  // they hold a snapshot of the old feature.
  useEffect(() => {
    if (!isReady || !gridData) return;
    mapRef.current?.getSource(GRID.source)?.setData(gridData);
    setTooltip(null);
  }, [isReady, gridData]);

  useEffect(() => {
    if (!isReady || !districtData) return;
    mapRef.current?.getSource(DISTRICTS.source)?.setData(districtData);
    setTooltip(null);
  }, [isReady, districtData]);

  useEffect(() => {
    if (!isReady) return;
    applyViewVisibility(mapRef.current, view);
    // The hidden layer never fires mouseleave, so its hover state must be
    // dropped here or the feature comes back still highlighted.
    clearHover();
    setTooltip(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isReady, view]);

  useEffect(() => {
    if (!isReady) return;
    mapRef.current?.setFilter(GRID.layers.selected, [
      '==', ['get', GRID.promoteId], selectedCellId ?? '',
    ]);
  }, [isReady, selectedCellId]);

  useEffect(() => {
    if (!isReady) return;
    mapRef.current?.setFilter(DISTRICTS.layers.selected, [
      '==', ['get', DISTRICTS.promoteId], selectedDistrict ?? '',
    ]);
  }, [isReady, selectedDistrict]);

  return (
    <div className="relative h-full w-full">
      <div
        ref={containerRef}
        className="h-full w-full"
        role="application"
        aria-label="Groundwater risk map. Areas are coloured by current well-failure risk; click an area for details."
      />
      {tooltip && <RiskTooltip tooltip={tooltip} month={month} />}
      {(isLoading || !isReady) && <MapSkeleton />}
    </div>
  );
}

function addRiskLayers(map, config, { outlineOpacity, outlineWidth }) {
  map.addSource(config.source, {
    type: 'geojson',
    data: EMPTY_COLLECTION,
    promoteId: config.promoteId,
  });
  map.addLayer(
    {
      id: config.layers.fill,
      type: 'fill',
      source: config.source,
      paint: { 'fill-color': fillColorExpression(), 'fill-opacity': HOVER_OPACITY },
    },
    ANCHOR_LAYER_ID,
  );
  map.addLayer(
    {
      id: config.layers.outline,
      type: 'line',
      source: config.source,
      paint: {
        'line-color': '#1C2B33',
        'line-opacity': outlineOpacity,
        'line-width': outlineWidth,
      },
    },
    ANCHOR_LAYER_ID,
  );
  map.addLayer(
    {
      id: config.layers.selected,
      type: 'line',
      source: config.source,
      filter: ['==', ['get', config.promoteId], ''],
      paint: { 'line-color': '#1C2B33', 'line-width': 2.5 },
    },
    ANCHOR_LAYER_ID,
  );
}

function applyViewVisibility(map, view) {
  if (!map) return;
  const setVisibility = (id, shown) => {
    if (map.getLayer(id)) {
      map.setLayoutProperty(id, 'visibility', shown ? 'visible' : 'none');
    }
  };
  // Basemap: satellite for the risk views, the street basemap for roads.
  const isRoads = view === 'roads';
  SATELLITE_BASEMAP_LAYERS.forEach((id) => setVisibility(id, !isRoads));
  setVisibility(STREET_BASEMAP_LAYER, isRoads);
  Object.values(GRID.layers).forEach((id) => setVisibility(id, view === 'grid'));
  Object.values(DISTRICTS.layers).forEach((id) => setVisibility(id, view === 'districts'));
}

function RiskTooltip({ tooltip, month }) {
  const { x, y, kind, props } = tooltip;
  const title = kind === 'district' ? props.district_name : formatCellName(props.cell_id);
  const hasData = props.current_risk != null;
  const band = hasData ? riskBand(props.current_risk) : null;
  const trend = hasData ? trendInfo(props.trend) : null;
  return (
    <div
      className="pointer-events-none absolute z-20 w-56 -translate-y-full animate-fade-up"
      style={{ left: Math.min(x + 14, window.innerWidth - 250), top: y - 14 }}
      role="tooltip"
    >
      <div className="card p-3">
        <p className="font-display text-sm font-semibold leading-tight">{title}</p>
        {hasData ? (
          <div className="mt-2 flex items-center justify-between gap-2">
            <span
              className="rounded-md px-2 py-0.5 font-mono text-sm font-semibold"
              style={{ backgroundColor: band.color, color: band.onColor }}
            >
              {Number(props.current_risk).toFixed(1)}
            </span>
            <span className="text-xs font-medium text-ink-soft">
              {band.label} · {trend.arrow} {trend.label}
            </span>
          </div>
        ) : (
          <p className="mt-2 text-xs font-medium text-ink-soft">
            No data — outside satellite coverage
          </p>
        )}
        <p className="microlabel mt-2">
          {kind === 'district' ? 'District average · ' : ''}Updated {formatMonth(month)}
        </p>
      </div>
    </div>
  );
}
