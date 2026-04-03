import { useState, useEffect } from "react"

const ADDUCTS = [
  { label: "[M+H]+",    api: "[M+H]+" },
  { label: "[M+Na]+",   api: "[M+Na]+" },
  { label: "[M+K]+",    api: "[M+K]+" },
  { label: "[M+NH4]+",  api: "[M+NH4]+" },
  { label: "[M-H]-",    api: "[M-H]-" },
  { label: "[M+Cl]-",   api: "[M+Cl]-" },
  { label: "[M+FA-H]-", api: "[M+FA-H]-" },
  { label: "[M]+",      api: "[M]+" },
  { label: "[M-2H]-",   api: "[M-2H]-" },
  { label: "[M-2H]2-",  api: "[M-2H]2-" },
  { label: "Neutral",   api: "neutral" },
]

const SOURCES = ["HMDB", "ChEBI", "LipidMaps", "NPAtlas"]

const SOURCE_COLORS = {
  HMDB:      { dot: "bg-blue-400",    text: "text-blue-400" },
  ChEBI:     { dot: "bg-emerald-400", text: "text-emerald-400" },
  LipidMaps: { dot: "bg-orange-400",  text: "text-orange-400" },
  NPAtlas:   { dot: "bg-purple-400",  text: "text-purple-400" },
}

export default function SearchPanel({ onSearch, loading }) {
  const [mode, setMode]               = useState("mass")
  const [massText, setMassText]       = useState("")
  const [formulaText, setFormulaText] = useState("")
  const [nameText, setNameText]       = useState("")
  const [ms2Text, setMs2Text]         = useState("")
  const [ms2Adduct, setMs2Adduct]     = useState("[M+H]+")
  const [tolerance, setTolerance]     = useState("0.02")
  const [topN, setTopN]               = useState("20")
  const [adducts, setAdducts]         = useState({ "[M+H]+": true })
  const [sources, setSources]         = useState(
    Object.fromEntries(SOURCES.map(s => [s, true]))
  )
  const [stats, setStats] = useState(null)

  useEffect(() => {
    fetch("https://api.lucid-lcms.org/stats")
      .then(r => r.json())
      .then(setStats)
      .catch(() => {})
  }, [])

  function toggleAdduct(api) {
    setAdducts(prev => ({ ...prev, [api]: !prev[api] }))
  }

  function toggleSource(src) {
    setSources(prev => ({ ...prev, [src]: !prev[src] }))
  }

  function handleSubmit(e) {
    e.preventDefault()

    const selectedAdducts = Object.entries(adducts).filter(([,v]) => v).map(([k]) => k)
    const selectedSources = Object.entries(sources).filter(([,v]) => v).map(([k]) => k)

    if (mode === "mass") {
      if (!selectedAdducts.length) { alert("Select at least one adduct."); return }

      const masses = massText
        .split(/[\n,\s]+/)
        .map(s => s.trim())
        .filter(Boolean)
        .map(Number)
        .filter(n => !isNaN(n) && n > 0)

      if (!masses.length) { alert("Enter at least one valid mass."); return }

      onSearch({
        masses,
        adducts:   selectedAdducts,
        tolerance: parseFloat(tolerance) || 0.02,
        sources:   selectedSources.length ? selectedSources : null,
        limit:     parseInt(topN) || 20,
      })

    } else if (mode === "formula") {
      const formulas = formulaText.split(/[\n,]+/).map(s => s.trim()).filter(Boolean)
      if (!formulas.length) { alert("Enter at least one formula."); return }

      onSearch({
        masses: [],
        adducts: ["neutral"],
        tolerance: 0,
        sources: selectedSources.length ? selectedSources : null,
        limit: parseInt(topN) || 100,
        _formulas: formulas,
      })

    } else if (mode === "name") {
      const query = nameText.trim()
      if (!query) { alert("Enter a compound name."); return }

      onSearch({
        masses: [],
        adducts: ["neutral"],
        tolerance: 0,
        sources: selectedSources.length ? selectedSources : null,
        limit: parseInt(topN) || 50,
        _name: query,
      })

    } else if (mode === "ms2") {
      const frags = ms2Text
        .split(/[\n,\s]+/)
        .map(s => s.trim())
        .filter(Boolean)
        .map(Number)
        .filter(n => !isNaN(n) && n > 0)

      if (frags.length < 2) {
        alert("Enter at least 2 fragment masses.")
        return
      }

      onSearch({
        masses: [],
        adducts: [ms2Adduct],
        tolerance: parseFloat(tolerance) || 0.02,
        sources: selectedSources.length ? selectedSources : null,
        limit: parseInt(topN) || 20,
        _ms2: { fragments: frags, adduct: ms2Adduct },
      })
    }
  }

  const inputClass = `w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2
    text-gray-100 text-sm font-mono placeholder-gray-600
    focus:outline-none focus:border-cyan-500/60 focus:ring-1 focus:ring-cyan-500/20
    transition-colors`

  const labelClass = "text-[11px] font-medium text-gray-500 uppercase tracking-widest mb-1.5 block"

  const MODES = [
    { key: "mass",    label: "Mass Search" },
    { key: "formula", label: "Formula Search" },
    { key: "name",    label: "Name Search" },
    { key: "ms2",     label: "MS2 Pattern" },
  ]

  return (
    <form onSubmit={handleSubmit} className="panel rounded-xl p-6 backdrop-blur-sm">

      {/* Stats bar */}
      {stats && (
        <div className="flex flex-wrap items-center gap-4 mb-5 pb-4 border-b border-gray-800">
          {SOURCES.map(src => (
            <div key={src} className="flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${SOURCE_COLORS[src]?.dot || 'bg-gray-500'}`}></span>
              <span className="text-[11px] text-gray-500">{src}</span>
              <span className="text-[11px] font-mono text-gray-400">
                {stats.by_source[src]?.toLocaleString() || '—'}
              </span>
            </div>
          ))}
          <div className="ml-auto text-[11px] font-mono text-cyan-500/70">
            {stats.total_compounds?.toLocaleString()} compounds
          </div>
        </div>
      )}

      <div className="flex flex-col lg:flex-row gap-6">

        {/* Left */}
        <div className="flex-1 flex flex-col gap-4">

          {/* Mode toggle */}
          <div className="flex gap-1 bg-gray-950 rounded-lg p-1 w-fit">
            {MODES.map(({ key, label }) => (
              <button
                key={key}
                type="button"
                onClick={() => setMode(key)}
                className={`px-4 py-1.5 rounded-md text-xs font-medium transition-all
                  ${mode === key
                    ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                    : "text-gray-500 hover:text-gray-300"}`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* MASS */}
          {mode === "mass" && (
            <>
              <textarea
                value={massText}
                onChange={e => setMassText(e.target.value)}
                placeholder={"181.071\n194.079\n342.116"}
                rows={4}
                className={inputClass + " resize-none"}
              />
            </>
          )}

          {/* FORMULA */}
          {mode === "formula" && (
            <textarea
              value={formulaText}
              onChange={e => setFormulaText(e.target.value)}
              placeholder={"C6H12O6\nC12H22O11"}
              rows={4}
              className={inputClass + " resize-none"}
            />
          )}

          {/* NAME */}
          {mode === "name" && (
            <input
              type="text"
              value={nameText}
              onChange={e => setNameText(e.target.value)}
              placeholder="e.g. caffeine"
              className={inputClass}
            />
          )}

          {/* MS2 */}
          {mode === "ms2" && (
            <>
              <textarea
                value={ms2Text}
                onChange={e => setMs2Text(e.target.value)}
                rows={5}
                className={inputClass + " resize-none"}
              />
            </>
          )}

        </div>

        {/* Right */}
        <div className="flex flex-col gap-5 lg:w-56">

          <button
            type="submit"
            disabled={loading}
            className={`w-full py-2.5 rounded-lg text-sm font-medium transition-all
              ${loading
                ? "bg-gray-800 text-gray-600 cursor-not-allowed"
                : "bg-gradient-to-r from-cyan-500 to-teal-400 text-black hover:brightness-110"}`}
          >
            {loading ? "searching..." : "Search →"}
          </button>

        </div>
      </div>
    </form>
  )
}