import { useState } from "react"
import SearchPanel from "./components/SearchPanel"
import ResultsTable from "./components/ResultsTable"
import FilterBar from "./components/FilterBar"

export default function App() {
  const [results, setResults]       = useState([])
  const [loading, setLoading]       = useState(false)
  const [error, setError]           = useState(null)
  const [filterTerm, setFilterTerm] = useState("")
  const [searched, setSearched]     = useState(false)
  const [expanded, setExpanded]     = useState(false)
  const [showAbout, setShowAbout]   = useState(false)

  async function handleSearch(params) {
    setLoading(true)
    setError(null)
    setFilterTerm("")
    setSearched(true)

    try {
      let data

      if (params._name) {
        // Name search
        const url = `https://api.lucid-lcms.org/search/name?query=${encodeURIComponent(params._name)}&limit=${params.limit}${params.sources ? '&sources=' + params.sources.join(',') : ''}`
        const res = await fetch(url)
        if (!res.ok) throw new Error(`Server error: ${res.status}`)
        const r = await res.json()
        data = [{
          query_mass: params._name,
          adduct: 'name',
          adduct_delta: 0,
          result_count: r.length,
          results: r.map(c => ({ ...c, adduct: 'N/A', mass_error: null, ppm_error: null }))
        }]
      } else if (params._formulas) {
        data = []
        for (const formula of params._formulas) {
          const url = `https://api.lucid-lcms.org/search/formula?formula=${encodeURIComponent(formula)}&limit=${params.limit}${params.sources ? '&sources=' + params.sources.join(',') : ''}`
          const res = await fetch(url)
          if (!res.ok) throw new Error(`Server error: ${res.status}`)
          const r = await res.json()
          data.push({
            query_mass: formula,
            adduct: 'formula',
            adduct_delta: 0,
            result_count: r.length,
            results: r.map(c => ({ ...c, adduct: 'N/A', mass_error: null, ppm_error: null }))
          })
        }
      } else {
        const res = await fetch(`https://api.lucid-lcms.org/search/batch`, {
          method:  "POST",
          headers: { "Content-Type": "application/json" },
          body:    JSON.stringify(params),
        })
        if (!res.ok) throw new Error(`Server error: ${res.status}`)
        data = await res.json()
      }

      setResults(data)
    } catch (e) {
      setError(e.message)
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const totalHits = results.reduce((sum, q) => sum + q.results.length, 0)

  return (
    <div style={{ fontFamily: "'IBM Plex Mono', 'Courier New', monospace" }}
         className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">

      {/* Google Font import via style tag */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

        * { box-sizing: border-box; }

        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #0a0f1a; }
        ::-webkit-scrollbar-thumb { background: #1e3a5f; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #0e7490; }

        .lucid-glow { box-shadow: 0 0 20px rgba(6, 182, 212, 0.15); }
        .lucid-border { border: 1px solid rgba(6, 182, 212, 0.2); }

        .result-row { transition: background 0.1s; }
        .result-row:hover { background: rgba(6, 182, 212, 0.05) !important; }

        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .fade-in { animation: fadeIn 0.3s ease forwards; }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        .spin { animation: spin 0.8s linear infinite; }
      `}</style>

      {/* Header */}
      <header className="border-b border-cyan-900/40 bg-gray-950/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="w-full px-8 py-4 flex items-center gap-5">
          <div className="flex items-center gap-3">
            <img
              src="/lucid-icon.png"
              alt="LUCID"
              className="h-8 w-auto rounded object-contain"
              onError={e => e.target.style.display='none'}
            />
            <div>
              <span style={{ fontFamily: "'IBM Plex Sans', sans-serif" }}
                    className="text-white font-semibold text-xl tracking-tight">
                LUCID
              </span>
              <span className="text-cyan-500/60 text-xs ml-3 hidden sm:inline">
                LC-MS Unified Compound Identification Database
              </span>
            </div>
          </div>

          <div className="ml-auto flex items-center gap-6 text-[12px] text-gray-500">
            <span className="hidden md:flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 inline-block"></span>
              HMDB · ChEBI · LipidMaps · NPAtlas
            </span>
            <button
              onClick={() => setShowAbout(a => !a)}
              className="text-gray-500 hover:text-cyan-400 transition-colors">
              About
            </button>
            <a href="https://github.com/elaneshan/mass-lookup-app"
               target="_blank" rel="noreferrer"
               className="text-gray-500 hover:text-cyan-400 transition-colors">
              GitHub ↗
            </a>
          </div>
        </div>
      </header>

      {/* About modal */}
      {showAbout && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center fade-in"
          onClick={() => setShowAbout(false)}
        >
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="relative z-10 bg-gray-900 border border-cyan-900/40 rounded-2xl
                       p-8 max-w-lg w-full mx-4 shadow-2xl flex flex-col gap-5"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h2 style={{ fontFamily: "'IBM Plex Sans', sans-serif" }}
                  className="text-white font-semibold text-lg">About LUCID</h2>
              <button onClick={() => setShowAbout(false)}
                      className="text-gray-600 hover:text-gray-300 transition-colors text-lg leading-none">
                ✕
              </button>
            </div>

            <p className="text-gray-400 text-sm leading-relaxed">
              LUCID is an open-source LC-MS compound identification tool that unifies
              search across 500k+ compounds from HMDB, ChEBI, LipidMaps, NPAtlas,
              FooDB, and PubChem — built to accelerate metabolomics research workflows.
            </p>

            <div className="grid grid-cols-2 gap-4 text-[12px]">
              <div className="flex flex-col gap-1">
                <span className="text-gray-600 uppercase tracking-widest text-[10px]">Developed by</span>
                <a href="https://www.linkedin.com/in/elane-shane" target="_blank" rel="noreferrer"
                   className="text-gray-200 text-sm hover:text-cyan-400 transition-colors">
                  Elane Shane ↗
                </a>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-gray-600 uppercase tracking-widest text-[10px]">Advisor</span>
                <span className="text-gray-300 font-medium">Ben Katz</span>
                <span className="text-gray-500">Mass Spectrometry Facility</span>
                <span className="text-gray-500">UC Irvine</span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-gray-600 uppercase tracking-widest text-[10px]">Source Code</span>
                <a href="https://github.com/elaneshan/mass-lookup-app"
                   target="_blank" rel="noreferrer"
                   className="text-cyan-400 hover:text-cyan-300 transition-colors">
                  GitHub ↗
                </a>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-gray-600 uppercase tracking-widest text-[10px]">Contact</span>
                <a href="https://github.com/elaneshan/mass-lookup-app/issues"
                   target="_blank" rel="noreferrer"
                   className="text-cyan-400 hover:text-cyan-300 transition-colors">
                  Open an issue ↗
                </a>
              </div>
            </div>

            <div className="pt-3 border-t border-gray-800 text-[11px] text-gray-600">
              Citation pending · MIT License
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-col flex-1 px-4 py-5 gap-4 max-w-screen-2xl mx-auto w-full">

        {!expanded && (
          <div className="fade-in">
            <SearchPanel onSearch={handleSearch} loading={loading} />
          </div>
        )}

        {searched && (
          <div className="flex items-center gap-3">
            <FilterBar value={filterTerm} onChange={setFilterTerm} />
            <button
              onClick={() => setExpanded(e => !e)}
              className="ml-auto text-[11px] px-3 py-1.5 rounded lucid-border
                         text-gray-400 hover:text-cyan-400 hover:border-cyan-500/40
                         transition-colors bg-gray-900 whitespace-nowrap"
            >
              {expanded ? "↓ Collapse" : "↑ Expand"}
            </button>
            {totalHits > 0 && (
              <span className="text-[11px] text-gray-500 whitespace-nowrap font-mono">
                {totalHits.toLocaleString()} hit{totalHits !== 1 ? "s" : ""}
              </span>
            )}
          </div>
        )}

        {error && (
          <div className="lucid-border rounded-lg px-4 py-3 text-sm text-red-400
                          bg-red-950/30 fade-in">
            Could not reach server: {error}
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-20 gap-3 text-gray-500 text-sm fade-in">
            <svg className="spin w-5 h-5 text-cyan-500" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-20" cx="12" cy="12" r="10"
                      stroke="currentColor" strokeWidth="3"/>
              <path className="opacity-80" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
            </svg>
            <span style={{ fontFamily: "'IBM Plex Mono'" }} className="text-xs">
              searching...
            </span>
          </div>
        )}

        {searched && !loading && !error && totalHits === 0 && (
          <div className="text-center py-20 text-gray-600 text-sm fade-in">
            No compounds found.
          </div>
        )}

        {!loading && totalHits > 0 && (
          <div className="fade-in">
            <ResultsTable queryResults={results} filterTerm={filterTerm} />
          </div>
        )}

      </div>

      <footer className="text-center text-[10px] text-gray-700 py-4 border-t border-gray-900">
        LUCID · Open source · Citation pending
      </footer>

    </div>
  )
}