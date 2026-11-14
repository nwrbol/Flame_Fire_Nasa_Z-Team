import { useEffect, useState } from 'react'
import Flame from './Flame.jsx'
import { getMaterials, simulate, ask } from './api.js'

const RISK = { low: 'Безопасно', medium: 'Средний риск', high: 'Высокий риск' }
const EXAMPLES = [
  'Почему пламя в невесомости круглое?',
  'Можно ли тушить огонь водой на МКС?',
  'Что опаснее: больше кислорода или сильнее поток?',
]

function Slider({ label, unit, value, min, max, onChange }) {
  return (
    <label className="field">
      <span>{label}: <b>{value} {unit}</b></span>
      <input type="range" min={min} max={max} value={value} onChange={(e) => onChange(+e.target.value)} />
    </label>
  )
}

export default function App() {
  const [tab, setTab] = useState('sim')
  const [materials, setMaterials] = useState([])
  const [p, setP] = useState({ material: 'polystyrene', o2: 21, flow: 5, co2: 0 })
  const [res, setRes] = useState(null)
  const [chat, setChat] = useState([])
  const [msg, setMsg] = useState('')

  useEffect(() => { getMaterials().then(setMaterials) }, [])
  useEffect(() => {
    const t = setTimeout(() => simulate(p).then(setRes), 250)
    return () => clearTimeout(t)
  }, [p])

  const set = (k) => (v) => setP((o) => ({ ...o, [k]: v }))

  const send = async (text) => {
    const q = (text ?? msg).trim()
    if (!q) return
    setMsg('')
    setChat((c) => [...c, { who: 'you', text: q }])
    const r = await ask(q)
    setChat((c) => [...c, { who: 'ai', text: r.answer }])
  }

  return (
    <div className="app">
      <main className="stage">
        <Flame rate={res?.spread_rate_mm_s ?? 0} risk={res?.risk ?? 'low'} />
        <header className="brand">
          <h1>CosmoFire</h1>
          <p>Так горит огонь в невесомости. Меняйте условия и смотрите, что станет с пламенем.</p>
        </header>
        {res && (
          <div className="readout">
            <p className={'state ' + res.risk}>{RISK[res.risk]}</p>
            <div className="nums">
              <div><b>{res.spread_rate_mm_s}</b><span>мм/с, скорость фронта</span></div>
              <div><b>{res.extinction_time_s}</b><span>с до затухания</span></div>
            </div>
          </div>
        )}
      </main>

      <aside className="side">
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === 'sim'} onClick={() => setTab('sim')}>Симулятор</button>
          <button role="tab" aria-selected={tab === 'chat'} onClick={() => setTab('chat')}>Вопросы</button>
        </div>

        {tab === 'sim' ? (
          <div className="pane">
            <label className="field">
              <span>Материал</span>
              <select value={p.material} onChange={(e) => set('material')(e.target.value)}>
                {materials.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            </label>
            <Slider label="Кислород (O2)" unit="%" value={p.o2} min={15} max={40} onChange={set('o2')} />
            <Slider label="Скорость потока" unit="см/с" value={p.flow} min={0} max={50} onChange={set('flow')} />
            <Slider label="Углекислый газ (CO2)" unit="%" value={p.co2} min={0} max={30} onChange={set('co2')} />
            {res && <p className={'note ' + res.risk}>{res.explanation}</p>}
          </div>
        ) : (
          <div className="pane">
            <div className="log" aria-live="polite">
              {chat.length === 0 && <p className="empty">Задайте вопрос или выберите пример.</p>}
              {chat.map((m, i) => <p key={i} className={'msg ' + m.who}>{m.text}</p>)}
            </div>
            {chat.length === 0 && (
              <div className="chips">
                {EXAMPLES.map((q) => <button key={q} className="chip" onClick={() => send(q)}>{q}</button>)}
              </div>
            )}
            <div className="ask">
              <input value={msg} placeholder="Ваш вопрос" onChange={(e) => setMsg(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && send()} />
              <button className="go" onClick={() => send()}>Спросить</button>
            </div>
          </div>
        )}
      </aside>
    </div>
  )
}
