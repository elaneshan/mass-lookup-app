import { useState, useEffect } from "react"

const ADDUCTS = [
  { label: "[M+H]+",     api: "[M+H]+" },
  { label: "[M+Na]+",    api: "[M+Na]+" },
  { label: "[M+K]+",     api: "[M+K]+" },
  { label: "[M+NH4]+",   api: "[M+NH4]+" },
  { label: "[M-H]-",     api: "[M-H]-" },
  { label: "[M+Cl]-",    api: "[M+Cl]-" },
  { label: "[M+FA-H]-",  api: "[M+FA-H]-" },
  { label: "Neutral",    api: "neutral" },
]

const SOURCES = ["HMDB", "ChEBI", "LipidMaps", "NPAtlas"]

export default function SearchPanel({ onSearch, loading }) {
  const [mode, setMode]             = useState("mass")   // "mass" | "formula"
  const [massText, setMassText]     = useState("")
  const [formulaText, setFormulaText] = useState("")
  const [tolerance, setTolerance]   = useState("0.02")
  const [topN, setTopN]             = useState("20")
  const [adducts, setAdducts]       = useState({ "[M+H]+": true })
  const [sources, setSources]       = useState(
    Object.fromEntries(SOURCES.map(s => [s, true]))
  )
  const [stats, setStats]           = useState(null)

  // Load DB stats on mount
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

    const selectedAdducts = Object.entries(adducts)
      .filter(([, v]) => v).map(([k]) => k)
    const selectedSources = Object.entries(sources)
      .filter(([, v]) => v).map(([k]) => k)

    if (selectedAdducts.length === 0) {
      alert("Select at least one adduct.")
      return
    }

    if (mode === "mass") {
      const masses = massText
        .split(/[\n,\s]+/)
        .map(s => s.trim())
        .filter(Boolean)
        .map(Number)
        .filter(n => !isNaN(n))

      if (masses.length === 0) {
        alert("Enter at least one valid mass.")
        return
      }

      onSearch({
        masses,
        adducts:   selectedAdducts,
        tolerance: parseFloat(tolerance) || 0.02,
        sources:   selectedSources.length > 0 ? selectedSources : null,
        limit:     parseInt(topN) || 20,
      })
    } else {
      // Formula mode — one query per formula using /search/formula endpoint
      // Wrap as pseudo-batch for unified results handling
      const formulas = formulaText
        .split(/[\n,]+/)
        .map(s => s.trim())
        .filter(Boolean)

      if (formulas.length === 0) {
        alert("Enter at least one formula.")
        return
      }

      onSearch({
        masses:    [],
        adducts:   ["neutral"],
        tolerance: 0,
        sources:   selectedSources.length > 0 ? selectedSources : null,
        limit:     parseInt(topN) || 100,
        _formulas: formulas,   // flag for App to use formula endpoint
      })
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white rounded-lg border border-slate-200 shadow-sm p-4"
    >
      {/* DB stats bar */}
      {stats && (
        <div className="flex flex-wrap gap-3 mb-3 text-xs text-slate-500">
          {Object.entries(stats.by_source).map(([src, cnt]) => (
            <span key={src}>
              <span className="font-medium text-slate-700">{src}</span>{" "}
              {cnt.toLocaleString()}
            </span>
          ))}
          <span className="ml-auto font-medium text-slate-700">
            {stats.total_compounds.toLocaleString()} total
          </span>
        </div>
      )}

      <div className="flex flex-col lg:flex-row gap-4">

        {/* Left — input */}
        <div className="flex-1 flex flex-col gap-3">

          {/* Mode toggle */}
          <div className="flex gap-2 text-sm">
            <button type="button"
              onClick={() => setMode("mass")}
              className={`px-3 py-1 rounded-full border text-xs font-medium transition-colors
                ${mode === "mass"
                  ? "bg-blue-900 text-white border-blue-900"
                  : "bg-white text-slate-600 border-slate-300 hover:border-blue-400"}`}
            >
              Mass Search
            </button>
            <button type="button"
              onClick={() => setMode("formula")}
              className={`px-3 py-1 rounded-full border text-xs font-medium transition-colors
                ${mode === "formula"
                  ? "bg-blue-900 text-white border-blue-900"
                  : "bg-white text-slate-600 border-slate-300 hover:border-blue-400"}`}
            >
              Formula Search
            </button>
          </div>

          {mode === "mass" ? (
            <>
              <label className="text-xs font-medium text-slate-600">
                Observed Masses (one per line or comma-separated)
              </label>
              <textarea
                value={massText}
                onChange={e => setMassText(e.target.value)}
                placeholder={"181.071\n194.079\n342.116"}
                rows={4}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm font-mono
                           focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              />
              <div className="flex gap-4 text-xs text-slate-600 items-center">
                <label className="flex items-center gap-1.5">
                  Tolerance (±)
                  <input
                    type="number" step="0.001" min="0.001" max="5"
                    value={tolerance}
                    onChange={e => setTolerance(e.target.value)}
                    className="w-20 rounded border border-slate-300 px-2 py-1 text-center
                               focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  Da
                </label>
                <label className="flex items-center gap-1.5">
                  Max results
                  <input
                    type="number" min="1" max="500"
                    value={topN}
                    onChange={e => setTopN(e.target.value)}
                    className="w-16 rounded border border-slate-300 px-2 py-1 text-center
                               focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </label>
              </div>
            </>
          ) : (
            <>
              <label className="text-xs font-medium text-slate-600">
                Molecular Formulas (one per line or comma-separated)
              </label>
              <textarea
                value={formulaText}
                onChange={e => setFormulaText(e.target.value)}
                placeholder={"C6H12O6\nC12H22O11"}
                rows={4}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm font-mono
                           focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              />
              <div className="flex gap-4 text-xs text-slate-600 items-center">
                <label className="flex items-center gap-1.5">
                  Max results
                  <input
                    type="number" min="1" max="500"
                    value={topN}
                    onChange={e => setTopN(e.target.value)}
                    className="w-16 rounded border border-slate-300 px-2 py-1 text-center
                               focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </label>
              </div>
            </>
          )}
        </div>

        {/* Right — adducts + sources */}
        <div className="flex flex-col gap-3 lg:w-64">

          {mode === "mass" && (
            <div>
              <p className="text-xs font-medium text-slate-600 mb-1.5">Adducts</p>
              <div className="grid grid-cols-2 gap-1">
                {ADDUCTS.map(({ label, api }) => (
                  <label key={api} className="flex items-center gap-1.5 text-xs cursor-pointer">
                    <input
                      type="checkbox"
                      checked={!!adducts[api]}
                      onChange={() => toggleAdduct(api)}
                      className="accent-blue-700"
                    />
                    <span className="font-mono">{label}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          <div>
            <p className="text-xs font-medium text-slate-600 mb-1.5">Databases</p>
            <div className="flex flex-col gap-1">
              {SOURCES.map(src => (
                <label key={src} className="flex items-center gap-1.5 text-xs cursor-pointer">
                  <input
                    type="checkbox"
                    checked={!!sources[src]}
                    onChange={() => toggleSource(src)}
                    className="accent-blue-700"
                  />
                  <span>{src}</span>
                  {stats && (
                    <span className="text-slate-400 ml-auto">
                      {stats.by_source[src]?.toLocaleString()}
                    </span>
                  )}
                </label>
              ))}
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="mt-auto w-full bg-green-600 hover:bg-green-700 disabled:bg-slate-300
                       text-white font-bold py-2 px-4 rounded text-sm transition-colors"
          >
            {loading ? "Searching..." : "Search"}
          </button>

        </div>
      </div>
    </form>
  )
}