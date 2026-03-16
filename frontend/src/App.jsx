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

  async function handleSearch(params) {
    setLoading(true)
    setError(null)
    setFilterTerm("")
    setSearched(true)

    try {
      const res = await fetch(`https://api.lucid-lcms.org/search/batch`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(params),
      })
      if (!res.ok) throw new Error(`Server error: ${res.status}`)
      const data = await res.json()
      setResults(data)
    } catch (e) {
      setError(e.message)
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  // Flatten results for counting
  const totalHits = results.reduce((sum, q) => sum + q.results.length, 0)

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">

      {/* Header */}
      <header className="bg-blue-900 text-white px-6 py-3 flex items-center gap-3 shadow-md">
        <img src="/lucid-icon.png" alt="LUCID" className="w-8 h-8" onError={e => e.target.style.display='none'} />
        <div>
          <h1 className="text-lg font-bold leading-tight">LUCID</h1>
          <p className="text-blue-200 text-xs leading-tight">LC-MS Unified Compound Identification Database</p>
        </div>
        <div className="ml-auto text-xs text-blue-300">
          HMDB · ChEBI · LipidMaps · NPAtlas
        </div>
      </header>

      <div className="flex flex-col flex-1 px-4 py-4 gap-3 max-w-screen-2xl mx-auto w-full">

        {/* Search panel — hide when expanded */}
        {!expanded && (
          <SearchPanel onSearch={handleSearch} loading={loading} />
        )}

        {/* Filter bar + expand button — only show after first search */}
        {searched && (
          <div className="flex items-center gap-3">
            <FilterBar value={filterTerm} onChange={setFilterTerm} />
            <button
              onClick={() => setExpanded(e => !e)}
              className="ml-auto text-xs px-3 py-1.5 rounded border border-slate-300 bg-white hover:bg-slate-50 text-slate-600 whitespace-nowrap"
            >
              {expanded ? "Collapse" : "Expand Results"}
            </button>
            {totalHits > 0 && (
              <span className="text-xs text-slate-500 whitespace-nowrap">
                {totalHits} match{totalHits !== 1 ? "es" : ""}
              </span>
            )}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded px-4 py-3 text-sm">
            Could not reach server: {error}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-12 text-slate-500 text-sm gap-2">
            <svg className="animate-spin h-5 w-5 text-blue-600" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
            </svg>
            Searching...
          </div>
        )}

        {/* No results */}
        {searched && !loading && !error && totalHits === 0 && (
          <div className="text-center py-12 text-slate-400 text-sm">
            No compounds found matching your search.
          </div>
        )}

        {/* Results */}
        {!loading && totalHits > 0 && (
          <ResultsTable
            queryResults={results}
            filterTerm={filterTerm}
          />
        )}

      </div>

      {/* Footer */}
      <footer className="text-center text-xs text-slate-400 py-3 border-t border-slate-200">
        LUCID · Open source · Cite: <em>citation pending</em>
      </footer>

    </div>
  )
}