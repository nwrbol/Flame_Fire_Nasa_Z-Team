// Если бэкенд недоступен, используются моки.
const MATERIALS = [
  { id: 'polystyrene', name: 'Полистирол' },
  { id: 'cotton', name: 'Хлопок' },
  { id: 'pmma', name: 'ПММА (оргстекло)' },
  { id: 'wire', name: 'Изоляция провода' },
]

function mockSim({ o2, flow, co2 }) {
  const rate = Math.max(0, 0.45 * (o2 - 15) * (1 + flow / 20) - 0.25 * co2)
  const risk = rate > 5 ? 'high' : rate > 2 ? 'medium' : 'low'
  return {
    spread_rate_mm_s: +rate.toFixed(2),
    extinction_time_s: rate < 0.3 ? 4 : +(60 / (rate + 1)).toFixed(1),
    risk,
    explanation: 'Мок-ответ: при таких параметрах риск оценён как ' + risk + '. Здесь будет текст от LLM.',
  }
}

async function call(url, opts, fallback) {
  try {
    const r = await fetch(url, opts)
    if (!r.ok) throw new Error('bad status')
    return await r.json()
  } catch {
    return fallback()
  }
}

const post = (url, body, fallback) =>
  call(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }, fallback)

export const getMaterials = () => call('/api/materials', {}, () => MATERIALS)
export const simulate = (p) => post('/api/simulate', p, () => mockSim(p))
export const ask = (message) =>
  post('/api/chat', { message }, () => ({ answer: 'Мок-ответ: здесь будет ответ LLM на вопрос "' + message + '".' }))
