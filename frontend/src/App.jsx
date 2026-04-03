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

        const fragments = Array.isArray(data.fragment_results)
          ? data.fragment_results.map(f => f.mass)
          : []

        const ladderInfo = detectFragmentLadders(fragments)

        const candidates = Array.isArray(data.candidates)
          ? data.candidates.map(c => {
              const normalized = {
                ...c,
                n_explained: c.fragments_explained ?? c.n_explained ?? 0,
                n_fragments: data.n_fragments ?? c.n_fragments ?? 0,
                score_pct:   c.coverage_pct ?? c.score_pct ?? 0,
                avg_ppm:     c.avg_ppm ?? 0,
                unmatched_fragments: Array.isArray(c.unmatched_fragments) ? c.unmatched_fragments : [],
                fragment_matches: Array.isArray(c.fragment_matches)
                  ? c.fragment_matches.map(m => ({
                      fragment_mass: m.fragment_mass,
                      ppm_error: m.ppm_error,
                      mass_error: m.mass_error,
                      neutral_mass: m.matched_mass ?? m.neutral_mass,
                    }))
                  : [],
              }

              normalized.smart_score = scoreCandidate(normalized, fragments, ladderInfo)
              return normalized
            })
          : []

        candidates.sort((a, b) => b.smart_score - a.smart_score)

        const normalized = {
          fragments,
          neutral_losses: Array.isArray(data.neutral_losses)
            ? data.neutral_losses.map(l => ({
                ...l,
                delta: l.loss_da ?? l.delta,
              }))
            : [],
          candidates,
          ladders: ladderInfo.ladders,
          ladderScore: ladderInfo.ladderScore,
          ladderEdges: ladderInfo.edges,
        }

        setMs2Result(normalized)

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

  function detectFragmentLadders(fragments, tolerance = 0.5) {
    const losses = [162.0528, 324.1056]
    const edges = []

    for (let i = 0; i < fragments.length; i++) {
      for (let j = 0; j < fragments.length; j++) {
        if (i === j) continue

        const from = fragments[i]
        const to   = fragments[j]
        const diff = from - to

        for (const loss of losses) {
          if (Math.abs(diff - loss) <= tolerance) {
            edges.push({ from, to, loss })
          }
        }
      }
    }

    const ladders = []

    function dfs(current, path, visited) {
      let extended = false

      for (const e of edges) {
        if (e.from === current && !visited.has(e.to)) {
          extended = true
          visited.add(e.to)
          dfs(e.to, [...path, e.to], visited)
          visited.delete(e.to)
        }
      }

      if (!extended && path.length > 1) {
        ladders.push(path)
      }
    }

    for (const f of fragments) {
      dfs(f, [f], new Set([f]))
    }

    // ✅ FIXED LADDER SCORING
    const longestLadder = ladders.reduce(
      (max, l) => Math.max(max, l.length),
      0
    )

    const ladderScore = Math.max(0, longestLadder - 1)

    return {
      ladders,
      ladderScore,
      longestLadder,
      edges
    }
  }

  function scoreCandidate(candidate, fragments, ladderInfo) {
    const fragmentMatches = Array.isArray(candidate.fragment_matches)
      ? candidate.fragment_matches
      : []

    const matchedMasses = new Set(fragmentMatches.map(m => m.fragment_mass))

    const matchScore = matchedMasses.size

    let ladderSupport = 0
    for (const edge of ladderInfo.edges) {
      if (matchedMasses.has(edge.from) && matchedMasses.has(edge.to)) {
        ladderSupport += 1
      }
    }

    let keyBonus = 0
    for (const f of fragments) {
      if (Math.abs(f - 303.05) < 0.5 && matchedMasses.has(f)) {
        keyBonus += 1.5
      }
    }

    // ✅ UPDATED PENALTY
    const penalty =
      matchedMasses.size === 0 ? 5 :
      matchedMasses.size === 1 ? 4 :
      0

    const rawScore = matchScore + (ladderSupport * 2) + keyBonus - penalty

    return Math.max(rawScore, 0)
  }

  const ladders = ms2Result?.ladders || []
  const ladderScore = ms2Result?.ladderScore || 0

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">

      {/* 🔥 HEADER BACK */}
      <header className="border-b border-cyan-900/40 bg-gray-950/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="w-full px-8 py-4 flex items-center gap-5">
          <div className="flex items-center gap-3">
            <img src="/lucid-icon.png" className="h-8 w-auto rounded" />
            <div>
              <span className="text-white font-semibold text-xl">LUCID</span>
              <span className="text-cyan-500/60 text-xs ml-3 hidden sm:inline">
                LC-MS Unified Compound Identification Database
              </span>
            </div>
          </div>

          <div className="ml-auto flex items-center gap-6 text-[12px] text-gray-500">
            <span className="hidden md:flex items-center gap-1.5">
              HMDB · ChEBI · LipidMaps · NPAtlas
            </span>
            <a href="https://github.com/elaneshan/mass-lookup-app" target="_blank" rel="noreferrer">
              GitHub ↗
            </a>
          </div>
        </div>

        <div className="text-[11px] text-gray-500 px-8 pb-2">
          {ladders.length} ladders · score: {ladderScore}
        </div>
      </header>

      <div className="flex flex-col flex-1 px-4 py-5 gap-4 max-w-screen-2xl mx-auto w-full">

        {!expanded && (
          <SearchPanel onSearch={handleSearch} loading={loading} />
        )}

        {searched && !loading && isMs2 && ms2Result && (
          <MS2ResultsTable ms2Result={ms2Result} />
        )}

        {!loading && !isMs2 && totalHits > 0 && (
          <ResultsTable queryResults={results} filterTerm={filterTerm} />
        )}

      </div>
    </div>
  )
}