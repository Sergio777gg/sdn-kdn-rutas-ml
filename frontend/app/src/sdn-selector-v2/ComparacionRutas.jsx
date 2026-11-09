import { COMPARISON_ROUTES } from './comparisonGraph.js';
import { useEffect, useRef, useState } from 'react';

const defaults = { delay: 0.5, loss: 0.35, capacity: 0.15, load: 0 };
const names = { delay: 'Delay', loss: 'Loss', capacity: 'Capacidad', load: 'Carga RX (opcional)' };
const fmt = (n, digits = 4) => n == null ? '—' : Number(n).toLocaleString('es-CO', { maximumFractionDigits: digits });

export default function ComparacionRutas({ live, apiUrl, origin, destination, result, onResult, visibility, onVisibility, onSelectLink, clock, onStart }) {
  const [weights, setWeights] = useState(defaults);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef(null);
  const epoch = useRef(0);
  const context = JSON.stringify([apiUrl, live.instanceId, live.graphVersion, live.snapshot.selection_revision, origin, destination, live.ready]);
  useEffect(() => () => { epoch.current += 1; pending.current?.abort(); }, [context]);

  async function calculate(event) {
    event.preventDefault();
    onStart();
    const generation = ++epoch.current;
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    const timeout = setTimeout(() => controller.abort(), 60000);
    setLoading(true); setError(''); onResult(null);
    try {
      const response = await fetch(`${apiUrl}/api/sdn/rutas/comparar`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ topology_instance_id: live.instanceId, graph_version: live.graphVersion,
          selection_revision: live.snapshot.selection_revision, origen: origin, destino: destination, pesos: weights }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Revisa los parametros de comparacion.');
      if (data.topology_instance_id !== live.instanceId || data.graph_version !== live.graphVersion ||
          data.selection_revision !== live.snapshot.selection_revision || data.session_id !== live.snapshot.session_id) {
        throw new Error('La respuesta pertenece a otra seleccion. Vuelve a comparar.');
      }
      if (!Array.isArray(data.alternativas) || data.alternativas.length !== 4 || COMPARISON_ROUTES.some(r => !data.alternativas.some(a => a.id === r.id))) throw new Error('El backend debe actualizarse para comparar los cuatro criterios.');
      if (epoch.current === generation) onResult(data);
    } catch (caught) {
      if (epoch.current === generation) setError(caught.name === 'AbortError' ? 'La comparacion tardo demasiado. Reintenta con una ventana reciente.' : caught.message);
    } finally {
      clearTimeout(timeout);
      if (epoch.current === generation) setLoading(false);
    }
  }
  const validWeights = Object.values(weights).every(n => Number.isFinite(n) && n >= 0) && Object.values(weights).some(n => n > 0);
  const routes = result?.alternativas || [];
  const routeLabels = Object.fromEntries(routes.map(r => [r.id, r.nombre]));
  const rows = [
    ['Saltos', 'saltos', '', 1],
    ['Retardo configurado acumulado', 'retardo_configurado_ms', ' ms', 1],
    ['Costo de referencia (misma fórmula: Σ 1/Mbps)', 'costo_referencia', '', 1],
    ['Costo QoS previsto (misma fórmula)', 'costo_qos', '', 1],
    ['Delay previsto acumulado', 'delay_previsto_ms', ' ms', 1],
    ['Loss previsto compuesto', 'loss_previsto_ratio', ' %', 100],
    ['Cuello de botella nominal', 'capacidad_minima_mbps', ' Mbps', 1],
  ];
  const rankings = Object.fromEntries((result?.mejores_por_metrica || []).map(r => [r.metrica, r]));
  return <div className="sdn-comparison" aria-live="polite">
    <style>{`.sdn-comparison{margin-top:24px;border-top:1px solid #28445e;padding-top:20px}.sdn-comparison h3{margin:0 0 12px}.sdn-qos-inputs,.sdn-comparison-cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.sdn-qos-inputs label{display:grid;gap:6px}.sdn-comparison-cards{margin-top:16px;grid-template-columns:repeat(4,minmax(0,1fr))}.sdn-comparison .sdn-best{display:inline-block;margin-left:6px;padding:2px 6px;border:1px solid #31775d;border-radius:8px;color:#86efac;font-size:10px}.sdn-comparison .sdn-delta{display:block;color:#91abc4;font-size:11px;margin-top:4px}.sdn-comparison-table{min-width:850px}.sdn-tradeoff{font-size:12px;line-height:1.5}.sdn-comparison .sdn-best-legend{font-size:12px;color:#91abc4}@media(max-width:1150px){.sdn-comparison-cards{grid-template-columns:repeat(2,minmax(0,1fr))}}.sdn-comparison-cards article{padding:16px;border:1px solid #345a7e;border-radius:10px}.sdn-route-legend{display:flex;gap:16px;flex-wrap:wrap;margin:14px 0}.sdn-route-legend label{display:flex;align-items:center;gap:6px}.sdn-comparison-cards p{overflow-wrap:anywhere}.sdn-comparison .primary-button{margin-top:14px}@media(max-width:760px){.sdn-comparison-cards{grid-template-columns:1fr}}`}</style>
    <h3>Comparación de rutas: los cuatro criterios</h3>
    <p className="sdn-muted">Origen {origin?.toUpperCase()} → destino {destination?.toUpperCase()}. Usa los selectores de arriba. Se comparan menos saltos, menor retardo configurado, inversa de capacidad y ML. Todas usan el mismo snapshot; las métricas previstas usan la misma ventana. La inversa de capacidad es la referencia de las diferencias.</p>
    <form onSubmit={calculate}>
      <details><summary>Pesos QoS configurables</summary><div className="sdn-qos-inputs">
        {Object.entries(names).map(([key, name]) => <label key={key}>{name}<input className="select-control" type="number" min="0" step="0.05" value={Number.isFinite(weights[key]) ? weights[key] : ''} onChange={e => {
          epoch.current += 1; pending.current?.abort(); setLoading(false); onResult(null);
          setWeights(previous => ({ ...previous, [key]: e.target.value === '' ? NaN : Number(e.target.value) }));
        }} /></label>)}
      </div><p className="sdn-muted">Se normalizan para sumar 1. Escalas: 50 ms, loss 1 %, capacidad 1 Mbps. Carga RX queda en 0 por defecto: poco trafico no implica un enlace malo. Al activarla, solo penaliza trafico RX cursado como proxy; no estima capacidad libre.</p></details>
      <button className="primary-button" disabled={loading || !live.ready || !origin || origin === destination || !validWeights}>{loading ? 'Comparando con predicciones recientes…' : 'Comparar rutas'}</button>
      {!validWeights && <p role="alert">Los pesos deben ser no negativos y sumar mas de cero.</p>}
    </form>
    {error && <p className="error-message" role="alert">{error}</p>}
    {result && <>
      <div className="sdn-comparison-cards">{routes.map(route => {
        const style = COMPARISON_ROUTES.find(r => r.id === route.id);
        return <article key={route.id} style={{ borderTop: `3px solid ${style.color}` }}><h3>{route.nombre}</h3>
          {route.status === 'available' ? <>
            <p>{route.ruta.map(n => n.toUpperCase()).join(' → ')}</p><p>{route.saltos} saltos</p>
            <p className="sdn-muted">Costo de su criterio: {fmt(route.costo_optimizacion, 6)} {route.unidad_optimizacion}.</p>
            {route.coincide_con?.length > 0 && <p className="sdn-muted">Mismo trayecto que: {route.coincide_con.map(id => routeLabels[id]).join(', ')}.</p>}
            {route.id === 'capacity' ? <p className="sdn-tradeoff">Referencia para las diferencias de esta comparación.</p> : <div className="sdn-tradeoff">
              <strong>Frente a la referencia por capacidad</strong>
              <p>Ventajas: {route.ventajas.length ? route.ventajas.join('; ') : 'sin mejoras en los indicadores comparables'}.</p>
              <p>Desventajas: {route.desventajas.length ? route.desventajas.join('; ') : 'sin valores peores en los indicadores comparables'}.</p>
            </div>}
            <button type="button" className="secondary-button" onClick={() => onVisibility(Object.fromEntries(COMPARISON_ROUTES.map(r => [r.id, r.id === route.id])))}>Ver solo esta ruta</button>
          </> : <p>{route.motivo}</p>}
        </article>;
      })}</div>
      <p><strong>{result.recomendacion}</strong></p>
      {result.todas_coinciden && <p className="sdn-muted">Los cuatro criterios eligieron el mismo trayecto. Es un resultado válido; las funciones de selección siguen siendo distintas.</p>}
      <p className="sdn-muted">Modelo: {result.ml.status === 'available' ? result.ml.modelo_id : 'sin predicciones utilizables'}. {result.ml.motivo}</p>
      {result.ml.feature_end_epoch_s && <p className="sdn-muted">Ventana fijada: {new Date(result.ml.feature_start_epoch_s * 1000).toLocaleTimeString('es-CO')} → {new Date(result.ml.feature_end_epoch_s * 1000).toLocaleTimeString('es-CO')}. Antigüedad: {fmt(clock / 1000 - result.ml.feature_end_epoch_s, 0)} s / {result.ml.max_age_s} s. Predice la ventana siguiente; no son mediciones extremo a extremo.</p>}
      <div className="sdn-route-legend" aria-label="Rutas en el mapa">
        {COMPARISON_ROUTES.map(style => <label key={style.id} style={{ color: style.color }}><input type="checkbox" checked={Boolean(visibility[style.id])} disabled={routes.find(r => r.id === style.id)?.status !== 'available'} onChange={e => onVisibility(v => ({ ...v, [style.id]: e.target.checked }))} /> {style.label}</label>)}
        <span>Dorado punteado: tramos compartidos entre rutas visibles.</span>
      </div>
      <p className="sdn-best-legend">«Mejor» indica el menor valor de costo, saltos, delay o loss, o la mayor capacidad mínima. «Empate» identifica alternativas que comparten el mejor valor. Las diferencias Δ se calculan frente a la ruta por inversa de capacidad.</p>
      <div className="sdn-table-scroll"><table className="sdn-table sdn-comparison-table"><caption>Comparación bajo métricas comunes del mismo snapshot y ventana</caption>
        <thead><tr><th>Indicador</th>{routes.map(route => <th key={route.id}>{route.nombre}</th>)}</tr></thead><tbody>
          {rows.map(([label, key, unit, multiplier]) => <tr key={key}><th scope="row">{label}</th>{routes.map(route => {
            const value = route[key];
            const delta = route.diferencias_vs_capacidad?.[key];
            return <td key={route.id}>{value == null ? '—' : `${fmt(value * multiplier)}${unit}`}
              {route.mejores_en?.includes(key) && <span className="sdn-best">{rankings[key]?.empate ? 'Empate' : 'Mejor'}</span>}
              {route.id !== 'capacity' && delta != null && <small className="sdn-delta">Δ {delta > 0 ? '+' : ''}{fmt(delta * multiplier)}{unit}</small>}
            </td>;
          })}</tr>)}
          <tr><th scope="row">Costo del criterio propio (escalas diferentes)</th>{routes.map(route => <td key={route.id}>{route.status === 'available' ? `${fmt(route.costo_optimizacion, 6)} ${route.unidad_optimizacion}` : 'No disponible'}</td>)}</tr>
        </tbody></table></div>
      <p className="sdn-muted">Los costos propios no se comparan numéricamente entre criterios: tienen distintas unidades. El costo QoS común y el costo de referencia sí se calculan con la misma fórmula para las cuatro rutas.</p>
      <details><summary>Método, pesos y limitaciones</summary><p className="sdn-muted">{result.formula}. Pesos usados: {Object.entries(result.pesos).map(([k,v]) => `${names[k]} ${fmt(v)}`).join(' · ')}.</p>
        {result.advertencias.map(text => <p className="sdn-muted" key={text}>{text}</p>)}
      </details>
      {routes.map(route => route.predicciones_enlaces?.length > 0 && <details key={route.id}><summary>Predicciones por enlace · {route.nombre}</summary>
        <div className="sdn-table-scroll"><table className="sdn-table"><caption>Predicciones fijadas a la ventana de esta comparación</caption><thead><tr><th>Dirección</th><th>RX Mbps</th><th>Delay ms</th><th>Loss %</th></tr></thead><tbody>
          {route.predicciones_enlaces.map(e => <tr key={e.link_id}><td><button type="button" className="sdn-table-link" onClick={() => onSelectLink(e.link_id)}>{e.origen.toUpperCase()} → {e.destino.toUpperCase()}</button></td><td>{fmt(e.throughput_rx_mbps)}</td><td>{fmt(e.delay_ms)}</td><td>{fmt(e.loss_ratio * 100)}</td></tr>)}
        </tbody></table></div>
      </details>)}
    </>}
  </div>;
}
