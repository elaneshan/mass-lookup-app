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
  const [tolerance, setTolerance]     = useState("0.02")
  const [topN, setTopN]               = useState("20")
  const [adducts, setAdducts]         = useState({ "[M+H]+": true })
  const [ms2Adduct, setMs2Adduct]     = useState("[M+H]+")
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
      const masses = massText.split(/[\n,\s]+/).map(s => s.trim()).filter(Boolean)
        .map(Number).filter(n => !isNaN(n) && n > 0)
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
        masses: [], adducts: ["neutral"], tolerance: 0,
        sources: selectedSources.length ? selectedSources : null,
        limit:   parseInt(topN) || 100,
        _formulas: formulas,
      })

    } else if (mode === "name") {
      const query = nameText.trim()
      if (!query) { alert("Enter a compound name."); return }
      onSearch({
        masses: [], adducts: ["neutral"], tolerance: 0,
        sources: selectedSources.length ? selectedSources : null,
        limit:   parseInt(topN) || 50,
        _name: query,
      })

    } else if (mode === "ms2") {
      const fragments = ms2Text.split(/[\n,\s]+/).map(s => s.trim()).filter(Boolean)
        .map(Number).filter(n => !isNaN(n) && n > 0)
      if (fragments.length < 2) { alert("Enter at least 2 fragment masses for pattern analysis."); return }
      if (fragments.length > 50) { alert("Maximum 50 fragment masses."); return }
      onSearch({
        masses: [], adducts: [ms2Adduct], tolerance: 0,
        sources: selectedSources.length ? selectedSources : null,
        limit:   parseInt(topN) || 20,
        _ms2: {
          fragment_masses: fragments,
          adduct:          ms2Adduct,
          tolerance:       parseFloat(tolerance) || 0.02,
          sources:         selectedSources.length ? selectedSources : null,
          limit:           parseInt(topN) || 20,
        },
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
    { key: "ms2",     label: "Flavonoid MS² Pattern" },
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

        {/* Left — input */}
        <div className="flex-1 flex flex-col gap-4">

          {/* Mode toggle */}
          <div className="flex gap-1 bg-gray-950 rounded-lg p-1 w-fit">
            {MODES.map(({ key, label }) => (
              <button
                key={key} type="button"
                onClick={() => setMode(key)}
                className={`px-4 py-1.5 rounded-md text-xs font-medium transition-all
                  ${mode === key
                    ? key === "ms2"
                      ? "bg-violet-500/20 text-violet-400 border border-violet-500/30"
                      : "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                    : "text-gray-500 hover:text-gray-300"}`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Mass mode */}
          {mode === "mass" && (
            <>
              <div>
                <label className={labelClass}>Observed Masses (m/z)</label>
                <textarea
                  value={massText}
                  onChange={e => setMassText(e.target.value)}
                  placeholder={"181.071\n194.079\n342.116"}
                  rows={4}
                  className={inputClass + " resize-none"}
                />
              </div>
              <div className="flex gap-5 items-end">
                <div>
                  <label className={labelClass}>Tolerance</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="number" step="0.001" min="0.001" max="5"
                      value={tolerance}
                      onChange={e => setTolerance(e.target.value)}
                      className={inputClass + " w-24 text-center"}
                    />
                    <span className="text-xs text-gray-500 font-mono">Da</span>
                  </div>
                </div>
                <div>
                  <label className={labelClass}>Max results</label>
                  <input
                    type="number" min="1" max="500"
                    value={topN}
                    onChange={e => setTopN(e.target.value)}
                    className={inputClass + " w-20 text-center"}
                  />
                </div>
              </div>
            </>
          )}

          {/* Formula mode */}
          {mode === "formula" && (
            <>
              <div>
                <label className={labelClass}>Molecular Formulas</label>
                <textarea
                  value={formulaText}
                  onChange={e => setFormulaText(e.target.value)}
                  placeholder={"C6H12O6\nC12H22O11"}
                  rows={4}
                  className={inputClass + " resize-none"}
                />
              </div>
              <div>
                <label className={labelClass}>Max results</label>
                <input
                  type="number" min="1" max="500"
                  value={topN}
                  onChange={e => setTopN(e.target.value)}
                  className={inputClass + " w-20 text-center"}
                />
              </div>
            </>
          )}

          {/* Name mode */}
          {mode === "name" && (
            <>
              <div>
                <label className={labelClass}>Compound Name</label>
                <input
                  type="text"
                  value={nameText}
                  onChange={e => setNameText(e.target.value)}
                  placeholder="e.g. caffeine, glucose, cholesterol"
                  className={inputClass}
                />
                <p className="text-[10px] text-gray-600 mt-1.5">
                  Partial matches supported — returns all compounds with names containing your query.
                </p>
              </div>
              <div>
                <label className={labelClass}>Max results</label>
                <input
                  type="number" min="1" max="500"
                  value={topN}
                  onChange={e => setTopN(e.target.value)}
                  className={inputClass + " w-20 text-center"}
                />
              </div>
            </>
          )}

          {/* MS2 Pattern Analysis mode */}
          {mode === "ms2" && (
            <>
              <div className="rounded-lg border border-violet-500/20 bg-violet-500/5 px-3 py-2.5">
                <p className="text-[11px] text-violet-300/70 leading-relaxed">
                  Paste all fragment masses from <strong className="text-violet-300">one MS² spectrum</strong>.
                  The engine scores candidate compounds by how many fragments they explain,
                  then detects neutral loss patterns across the spectrum.
                </p>
              </div>

              <div>
                <label className={labelClass}>Fragment Masses (m/z)</label>
                <textarea
                  value={ms2Text}
                  onChange={e => setMs2Text(e.target.value)}
                  placeholder={"1113.2891\n951.2382\n789.1868\n627.1363\n465.1033\n303.0502"}
                  rows={6}
                  className={inputClass + " resize-none"}
                />
                <p className="text-[10px] text-gray-600 mt-1.5">
                  One mass per line, or comma/space separated. Min 2, max 50 fragments.
                </p>
              </div>

              <div className="flex gap-5 items-end flex-wrap">
                <div>
                  <label className={labelClass}>Precursor adduct</label>
                  <select
                    value={ms2Adduct}
                    onChange={e => setMs2Adduct(e.target.value)}
                    className={inputClass + " w-36 cursor-pointer"}
                  >
                    {ADDUCTS.map(({ label, api }) => (
                      <option key={api} value={api}>{label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className={labelClass}>Tolerance</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="number" step="0.001" min="0.001" max="1"
                      value={tolerance}
                      onChange={e => setTolerance(e.target.value)}
                      className={inputClass + " w-24 text-center"}
                    />
                    <span className="text-xs text-gray-500 font-mono">Da</span>
                  </div>
                </div>
                <div>
                  <label className={labelClass}>Max candidates</label>
                  <input
                    type="number" min="1" max="50"
                    value={topN}
                    onChange={e => setTopN(e.target.value)}
                    className={inputClass + " w-20 text-center"}
                  />
                </div>
              </div>
            </>
          )}
        </div>

        {/* Right — adducts + sources + button */}
        <div className="flex flex-col gap-5 lg:w-56">

          {mode === "mass" && (
            <div>
              <label className={labelClass}>Adducts</label>
              <div className="grid grid-cols-2 gap-y-2 gap-x-3">
                {ADDUCTS.map(({ label, api }) => (
                  <label key={api} className="flex items-center gap-2 cursor-pointer group">
                    <div
                      onClick={() => toggleAdduct(api)}
                      className={`w-4 h-4 rounded border flex items-center justify-center
                        transition-all cursor-pointer flex-shrink-0
                        ${adducts[api]
                          ? "bg-cyan-500/20 border-cyan-500/60"
                          : "border-gray-700 group-hover:border-gray-500"}`}
                    >
                      {adducts[api] && (
                        <svg className="w-2.5 h-2.5 text-cyan-400" fill="none"
                             viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
                        </svg>
                      )}
                    </div>
                    <span className="text-[11px] font-mono text-gray-400 group-hover:text-gray-200
                                     transition-colors leading-none">
                      {label}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}

          <div>
            <label className={labelClass}>Databases</label>
            <div className="flex flex-col gap-2">
              {SOURCES.map(src => (
                <label key={src} className="flex items-center gap-2 cursor-pointer group">
                  <div
                    onClick={() => toggleSource(src)}
                    className={`w-4 h-4 rounded border flex items-center justify-center
                      transition-all cursor-pointer flex-shrink-0
                      ${sources[src]
                        ? "bg-cyan-500/20 border-cyan-500/60"
                        : "border-gray-700 group-hover:border-gray-500"}`}
                  >
                    {sources[src] && (
                      <svg className="w-2.5 h-2.5 text-cyan-400" fill="none"
                           viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
                      </svg>
                    )}
                  </div>
                  <span className={`text-[11px] font-medium transition-colors
                    ${sources[src]
                      ? SOURCE_COLORS[src]?.text || "text-gray-300"
                      : "text-gray-600 group-hover:text-gray-400"}`}>
                    {src}
                  </span>
                  {stats && (
                    <span className="ml-auto text-[10px] font-mono text-gray-600">
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
            className={`w-full py-2.5 rounded-lg text-sm font-medium transition-all
              ${loading
                ? "bg-gray-800 text-gray-600 cursor-not-allowed"
                : mode === "ms2"
                  ? "bg-gradient-to-r from-violet-500 to-purple-400 text-white hover:brightness-110"
                  : "bg-gradient-to-r from-cyan-500 to-teal-400 text-black hover:brightness-110"}`}
          >
            {loading
              ? "analyzing..."
              : mode === "ms2"
              ? "Analyze Pattern →"
              : "Search →"}
          </button>

        </div>
      </div>
    </form>
  )
}