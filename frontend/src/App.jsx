import { useState } from "react"
import SearchPanel from "./components/SearchPanel"
import ResultsTable from "./components/ResultsTable"
import FilterBar from "./components/FilterBar"

export default function App() {
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [filterTerm, setFilterTerm] = useState("")
  const [searched, setSearched] = useState(false)
  const [expanded, setExpanded] = useState(false)

  async function handleSearch(params) {
    setLoading(true)
    setError(null)
    setFilterTerm("")
    setSearched(true)

    try {
      let data

      if (params._formulas) {
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
            results: r.map(c => ({
              ...c,
              adduct: 'N/A',
              mass_error: null,
              ppm_error: null
            }))
          })
        }
      } else {
        const res = await fetch(`https://api.lucid-lcms.org/search/batch`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(params)
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
    <div
      style={{ fontFamily: "'IBM Plex Sans', system-ui" }}
      className="min-h-screen bg-[#0F1720] text-gray-200 flex flex-col"
    >

<style>{`
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@300;400;500&display=swap');

*{box-sizing:border-box}

::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:#0A0F14}
::-webkit-scrollbar-thumb{background:#1c2a38;border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:#00C2FF}

.result-row{
transition:background .12s ease;
}

.result-row:hover{
background:rgba(0,194,255,0.05);
}

.panel{
background:#131C26;
border:1px solid rgba(255,255,255,0.05);
}

`}</style>

<header className="border-b border-gray-800 bg-[#0A0F14] sticky top-0 z-50">
<div className="max-w-screen-2xl mx-auto px-6 py-3 flex items-center gap-4">

<div className="flex items-center gap-3">
<img
src="/lucid-icon.png"
alt="LUCID"
className="w-7 h-7 rounded"
/>

<div>
<span className="text-white font-semibold text-base">
LUCID
</span>

<span className="text-cyan-400/70 text-xs ml-2 hidden sm:inline">
LC-MS Unified Compound Identification Database
</span>
</div>
</div>

<div className="ml-auto flex items-center gap-4 text-[11px] text-gray-500">

<span className="hidden md:flex items-center gap-1.5">
<span className="w-1.5 h-1.5 rounded-full bg-cyan-400 inline-block"></span>
HMDB · ChEBI · LipidMaps · NPAtlas
</span>

<a
href="https://github.com/elaneshan/mass-lookup-app"
target="_blank"
rel="noreferrer"
className="hover:text-cyan-400 transition-colors"
>
GitHub ↗
</a>

</div>
</div>
</header>

<div className="flex flex-col flex-1 px-4 py-5 gap-4 max-w-screen-2xl mx-auto w-full">

{!expanded && (
<div>
<SearchPanel onSearch={handleSearch} loading={loading}/>
</div>
)}

{searched && (
<div className="flex items-center gap-3">

<FilterBar
value={filterTerm}
onChange={setFilterTerm}
/>

<button
onClick={()=>setExpanded(e=>!e)}
className="ml-auto text-[11px] px-3 py-1.5 rounded border border-gray-700 text-gray-400 hover:text-cyan-400 hover:border-cyan-400/40 bg-[#0F1720]"
>
{expanded ? "↓ Collapse" : "↑ Expand"}
</button>

{totalHits>0 &&(
<span className="text-[11px] text-gray-500 font-mono">
{totalHits.toLocaleString()} hits
</span>
)}

</div>
)}

{error &&(
<div className="panel rounded-lg px-4 py-3 text-sm text-red-400">
Could not reach server: {error}
</div>
)}

{loading &&(
<div className="flex justify-center py-20 text-gray-500 text-sm">
searching...
</div>
)}

{searched && !loading && !error && totalHits===0 &&(
<div className="text-center py-20 text-gray-600 text-sm">
No compounds found.
</div>
)}

{!loading && totalHits>0 &&(
<ResultsTable
queryResults={results}
filterTerm={filterTerm}
/>
)}

</div>

<footer className="text-center text-[10px] text-gray-700 py-4 border-t border-gray-900">
LUCID · Open source
</footer>

</div>
)
}