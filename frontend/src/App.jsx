import { useState } from "react"
import SearchPanel from "./components/SearchPanel"
import ResultsTable from "./components/ResultsTable"
import MS2ResultsTable from "./components/MS2ResultsTable"
import FilterBar from "./components/FilterBar"

export default function App() {
  const [results, setResults]       = useState([])
  const [ms2Result, setMs2Result]   = useState(null)
  const [searchMode, setSearchMode] = useState(null)
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
    setMs2Result(null)
    setResults([])

    try {
      if (params._ms2) {
        setSearchMode("ms2")

        const res = await fetch("https://api.lucid-lcms.org/search/ms2", {
          method:  "POST",
          headers: { "Content-Type": "application/json" },
          body:    JSON.stringify(params._ms2),
        })
        if (!res.ok) throw new Error(`Server error: ${res.status}`)
        const data = await res.json()
        console.log("API DATA:", data)

        // FIX 1: Use backend fragment list directly (backend returns fragment_results)
        const fragments = Array.isArray(data.fragment_results)
          ? data.fragment_results.map(f => f.mass)
          : []

        // FIX 1: Remove all client-side rescoring — use backend scores directly
        const candidates = Array.isArray(data.candidates)
          ? data.candidates.map(c => ({
              ...c,
              // FIX 3: n_explained from fragments_explained; n_fragments from top-level data
              n_explained:  c.fragments_explained ?? c.n_explained ?? 0,
              n_fragments:  data.n_fragments ?? 0,
              coverage_pct: c.coverage_pct ?? 0,
              avg_ppm:      c.avg_ppm ?? 0,
              unmatched_fragments: Array.isArray(c.unmatched_fragments) ? c.unmatched_fragments : [],
              fragment_matches: Array.isArray(c.fragment_matches)
                ? c.fragment_matches.map(m => ({
                    fragment_mass: m.fragment_mass,
                    ppm_error:     m.ppm_error,
                    mass_error:    m.mass_error,
                    neutral_mass:  m.matched_mass ?? m.neutral_mass,
                  }))
                : [],
            }))
          : []

        // Sort by backend coverage_pct (backend may already sort, but be explicit)
        candidates.sort((a, b) => b.coverage_pct - a.coverage_pct)

        // FIX 2: Pass neutral_losses through as-is — backend uses loss_da, consumer reads loss_da
        const normalized = {
          fragments,
          neutral_losses: Array.isArray(data.neutral_losses) ? data.neutral_losses : [],
          candidates,
        }

        setMs2Result(normalized)
        console.log("CAND0:", JSON.stringify(normalized.candidates[0], null, 2))
        console.log("FRAGS:", normalized.fragments)

      } else if (params._name) {
        setSearchMode("standard")

        const url = `https://api.lucid-lcms.org/search/name?query=${encodeURIComponent(params._name)}&limit=${params.limit}${params.sources ? '&sources=' + params.sources.join(',') : ''}`
        const res = await fetch(url)
        if (!res.ok) throw new Error(`Server error: ${res.status}`)
        const r = await res.json()

        setResults([{
          query_mass: params._name,
          adduct: 'name',
          adduct_delta: 0,
          result_count: r.length,
          results: r.map(c => ({ ...c, adduct: 'N/A', mass_error: null, ppm_error: null }))
        }])

      } else if (params._formulas) {
        setSearchMode("standard")

        const data = []
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

        setResults(data)

      } else {
        setSearchMode("standard")

        const res = await fetch(`https://api.lucid-lcms.org/search/batch`, {
          method:  "POST",
          headers: { "Content-Type": "application/json" },
          body:    JSON.stringify(params),
        })
        if (!res.ok) throw new Error(`Server error: ${res.status}`)
        setResults(await res.json())
      }

    } catch (e) {
      setError(e.message)
      setResults([])
      setMs2Result(null)
    } finally {
      setLoading(false)
    }
  }

  const totalHits = results.reduce((sum, q) => sum + q.results.length, 0)
  const isMs2     = searchMode === "ms2"

  return (
      <div style={{fontFamily: "'IBM Plex Mono', 'Courier New', monospace"}}
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
                  onError={e => e.target.style.display = 'none'}
              />
              <div>
              <span style={{fontFamily: "'IBM Plex Sans', sans-serif"}}
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
              <div className="absolute inset-0 bg-black/60 backdrop-blur-sm"/>
              <div
                  className="relative z-10 bg-gray-900 border border-cyan-900/40 rounded-2xl
                       p-8 max-w-lg w-full mx-4 shadow-2xl flex flex-col gap-5"
                  onClick={e => e.stopPropagation()}
              >
                <div className="flex items-center justify-between">
                  <h2 style={{fontFamily: "'IBM Plex Sans', sans-serif"}}
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
              <SearchPanel onSearch={handleSearch} loading={loading}/>
          )}

          {searched && !loading && isMs2 && ms2Result && (
              <MS2ResultsTable ms2Result={ms2Result}/>
          )}

          {!loading && !isMs2 && totalHits > 0 && (
              <ResultsTable queryResults={results} filterTerm={filterTerm}/>
          )}

        </div>
      </div>
  )
}