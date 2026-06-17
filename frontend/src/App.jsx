import { useState } from "react"
import SearchPanel from "./components/SearchPanel"
import ResultsTable from "./components/ResultsTable"
import MS2ResultsTable from "./components/MS2ResultsTable"
import FilterBar from "./components/FilterBar"
/*
App.jsx -> the main frontend controller, this is where the frontend
talks wih the backend.

dependeding on the searchmode type -> it sends requests to different endpoints
normalizes the data given back and renders the appropriate results table.

it does statemanagement -> communicates withthe API -> transforms the data
-> and does conditional rendering

the UI is sperated into resuable components so i can have the app
component just focus on the control logic rather than the presentation logic



*/


export default function App() {
  // ── Global state variables ──────────────────────────────────────────────
  // results: array of query results for standard searches (mass/formula/name)
  // ms2Result: single object for MS² pattern analysis results
  // searchMode: "ms2" or "standard" — controls which results table renders
  // loading: true while waiting for API response
  // error: holds error message string if request fails
  // searched: true once user has submitted at least one search (controls rendering)
  const [results, setResults]       = useState([])
  const [ms2Result, setMs2Result]   = useState(null) // seperated into its own state object bc the strcture is different than standard searches
  const [searchMode, setSearchMode] = useState(null) // UI needs to know what results table to render later, so this is used to track it
  const [loading, setLoading]       = useState(false) //prevents duplicate searches done, allows UI to show loading indicators
  const [error, setError]           = useState(null) // centralizing error handling
  const [filterTerm, setFilterTerm] = useState("") // for the filterbar
  const [searched, setSearched]     = useState(false) // this is here to track if the user has ever searched; so the UI can differenticate between 'no search yet' and 'search returned no results'
  const [expanded, setExpanded]     = useState(false)
  const [showAbout, setShowAbout]   = useState(false)

  // ── Main search handler ────────────────────────────────────────
  // Called by SearchPanel when user clicks Search
  // params object has different shapes depending on search mode:
  //   params._ms2      → MS² pattern analysis
  //   params._name     → name search
  //   params._formulas → formula search
  //   (none of above)  → batch mass search

  // this is the central API orchestration layer; it gets the search params from the SearchPanel component,
  // then it sends the correct request to the endpoints
  // normalizes that data that it gets back in the response
  // then updates the usestate so that the application can be rendered


  /*
  Overall flow here:
  1. user gives inputs and clicks search
  2. searchpanel will handle the calls the validation of everything
  3. it calls handlesearch is liek hey i have tjis info (all of the usestates are set), now i want you to gimme the resukts
  4. hnadlesearch will decte the searchtype (from usestate), then uses fetch to send over the HTTP request to the backend API
  5. then the backend will process the queery
  6. and it returns the response in the JSON file
  7. the front end then comes back and parses the JSON
  8. all of the states are updated
  9. and UI re-renders automatically based on the states (yay shoutout react!)
   */
  async function handleSearch(params) {
    // Reset all state before new search -> happens every time before startign a new request
    // everything here uses async bc the fronend needs to be able to communicate asynchronously with the API while also keepign the UI responsive
    setLoading(true)
    setError(null)
    setFilterTerm("")
    setSearched(true) // mark that the user searched
    setMs2Result(null)
    setResults([])

    // all of the async fetch operations are wrapped up in try/catch blocks
    try {
      // ── MS² Pattern Analysis branch ──────────────────────────
      if (params._ms2) {
        setSearchMode("ms2")

        // POST fragment masses + adduct + tolerance to MS² endpoint
        const res = await fetch("https://api.lucid-lcms.org/search/ms2", {
          method:  "POST", // not using get here! the ms2 data specifically is so complex and nested we can just use POST to send it over
          headers: { "Content-Type": "application/json" },
          body:    JSON.stringify(params._ms2), // send it clearly in the body
        }) // using await here, to stop execution until request is resolved
        // Throw immediately if server returns non-2xx status
        if (!res.ok) throw new Error(`Server error: ${res.status}`) // fetch only throws on netwrok faikures, not any HTTP failures liek 404 so i mannualy check all the response stats
        const data = await res.json() // then we can parse the json back

        // Extract fragment masses from fragment_results array
        // (backend returns {mass, hits} objects, we just need the mass values)
        const fragments = Array.isArray(data.fragment_results)
          ? data.fragment_results.map(f => f.mass)
          : []

        // NEXT IMPORTANT SECTION!
        // Normalize candidate field names: backend and frontend evolved
        // independently and field names drifted (had lots of errors with this...). So we addd a normalization layer that
        // maps backend names to what the components expect, with fallbacks.
        // e.g. backend sends "fragments_explained", component reads "n_explained"
        // reason for this: we don't want to have a million edge cases, which comes from the inconsistent backend responses
        // i centralized the transformation logic in the API layer
        const candidates = Array.isArray(data.candidates)
          ? data.candidates.map(c => ({
              ...c,
              n_explained:  c.fragments_explained ?? c.n_explained ?? 0, // example here: if fragments_explained is missing use the next one, or th enext one, or 0
              n_fragments:  data.n_fragments ?? 0,   // n_fragments is top-level, not per-candidate
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

        // Sort by coverage_pct descending, highest coverage first (backend already sorts but be explicit)
        candidates.sort((a, b) => b.coverage_pct - a.coverage_pct)

        // Build normalized result object that MS2ResultsTable expects
        // ladder_annotation contains the structural prediction (aglycone + sugar composition)
        const normalized = {
          fragments,
          neutral_losses: Array.isArray(data.neutral_losses) ? data.neutral_losses : [],
          candidates,
          ladder_annotation: data.ladder_annotation ?? null,
        }

        setMs2Result(normalized)

      // ── Name search branch ────────────────────────────────────
      } else if (params._name) {
        setSearchMode("standard") // this is the reg search with name

        // GET request with query string — name search is read-only so GET is appropriate
        const url = `https://api.lucid-lcms.org/search/name?query=${encodeURIComponent(params._name)}&limit=${params.limit}${params.sources ? '&sources=' + params.sources.join(',') : ''}`
        const res = await fetch(url)
        if (!res.ok) throw new Error(`Server error: ${res.status}`)
        const r = await res.json()

        // Wrap in same shape as batch results so ResultsTable can render it uniformly
        setResults([{
          query_mass: params._name,
          adduct: 'name',
          adduct_delta: 0,
          result_count: r.length,
          results: r.map(c => ({ ...c, adduct: 'N/A', mass_error: null, ppm_error: null }))
        }])

      // ── Formula search branch ─────────────────────────────────
      } else if (params._formulas) {
        setSearchMode("standard")

        // Formula search fires one request per formula sequentially
        // (could be parallelized with Promise.all but sequential is simpler and load is low)
        const data = []
        for (const formula of params._formulas) {
          const url = `https://api.lucid-lcms.org/search/formula?formula=${encodeURIComponent(formula)}&limit=${params.limit}${params.sources ? '&sources=' + params.sources.join(',') : ''}`
          const res = await fetch(url)
          if (!res.ok) throw new Error(`Server error: ${res.status}`)
          const r = await res.json()

          // so we already have a bunch of endpoints but the frontend only has <resultstable> for standard searches
          //so we need to give it a unified schema, which is what we do here, we kinda overload a few of the fields to get this done and prevent a bunch of conditional statements here
          // bc we do this we don't need to have like a resultstable component for formula, mass, name searchs
          data.push({
            query_mass: formula,
            adduct: 'formula',
            adduct_delta: 0,
            result_count: r.length,
            results: r.map(c => ({ ...c, adduct: 'N/A', mass_error: null, ppm_error: null }))
          })
        }
        setResults(data)

      // ── Batch mass search branch ──────────────────────────────
      } else {
        setSearchMode("standard")

        // POST all masses + adducts in one request
        // backend returns results grouped by mass/adduct pair
        const res = await fetch(`https://api.lucid-lcms.org/search/batch`, {
          method:  "POST",
          headers: { "Content-Type": "application/json" },
          body:    JSON.stringify(params),
        })
        if (!res.ok) throw new Error(`Server error: ${res.status}`)
        setResults(await res.json())
      }

    } catch (e) {
      // Any error (network, server 5xx, parsing) lands here
      // Sets error state which renders an error message in the UI
      setError(e.message)
      setResults([])
      setMs2Result(null)
    } finally {
      // Always clear loading regardless of success or failure
      setLoading(false)
    }
  }

  // Total number of compound hits across all queries (for standard search display)
  const totalHits = results.reduce((sum, q) => sum + q.results.length, 0)
  const isMs2     = searchMode === "ms2"

  // key thing to remeber is state -> determines UI!
  // it will auto re-render whenever the state changes
  return (
      <div style={{fontFamily: "'IBM Plex Mono', 'Courier New', monospace"}}
           className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
        {/* ... styles and header ... */}

        <div className="flex flex-col flex-1 px-4 py-5 gap-4 max-w-screen-2xl mx-auto w-full">

          {/* Search input panel — always visible unless expanded mode */}
          {!expanded && (
              <SearchPanel onSearch={handleSearch} loading={loading}/>
          )}

          {/* MS² results — only renders after search, in ms2 mode, with data */}
          {searched && !loading && isMs2 && ms2Result && (
              <MS2ResultsTable ms2Result={ms2Result}/>
          )}

          {/* Standard results — only renders in standard mode with hits */}
          {!loading && !isMs2 && totalHits > 0 && (
              <ResultsTable queryResults={results} filterTerm={filterTerm}/>
          )}

        </div>
      </div>
  )
}