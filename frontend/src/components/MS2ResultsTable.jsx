import { useState } from "react"

const SOURCE_COLORS = {
  HMDB:      { dot: "bg-blue-400",    badge: "bg-blue-400/10 text-blue-400 border-blue-400/20" },
  ChEBI:     { dot: "bg-emerald-400", badge: "bg-emerald-400/10 text-emerald-400 border-emerald-400/20" },
  LipidMaps: { dot: "bg-orange-400",  badge: "bg-orange-400/10 text-orange-400 border-orange-400/20" },
  NPAtlas:   { dot: "bg-purple-400",  badge: "bg-purple-400/10 text-purple-400 border-purple-400/20" },
}

const SOURCE_URLS = {
  HMDB:      id => `https://hmdb.ca/metabolites/${id}`,
  ChEBI:     id => `https://www.ebi.ac.uk/chebi/searchId.do?chebiId=${id}`,
  LipidMaps: id => `https://www.lipidmaps.org/databases/lmsd/${id}`,
  NPAtlas:   id => `https://www.npatlas.org/explore/compounds/${id}`,
}

const CONFIDENCE_STYLES = {
  high:     { bar: "bg-emerald-500", text: "text-emerald-400", border: "border-emerald-500/30", bg: "bg-emerald-500/5" },
  moderate: { bar: "bg-yellow-500",  text: "text-yellow-400",  border: "border-yellow-500/30",  bg: "bg-yellow-500/5"  },
  low:      { bar: "bg-orange-500",  text: "text-orange-400",  border: "border-orange-500/30",  bg: "bg-orange-500/5"  },
  none:     { bar: "bg-gray-600",    text: "text-gray-500",    border: "border-gray-700",        bg: "bg-gray-900/40"   },
}

function LadderAnnotationPanel({ annotation }) {
  if (!annotation) return null

  const conf = CONFIDENCE_STYLES[annotation.confidence] ?? CONFIDENCE_STYLES.none

  return (
    <div className={`rounded-xl border ${conf.border} ${conf.bg} p-5 flex flex-col gap-4`}>
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="text-[10px] text-gray-500 uppercase tracking-widest">
          Structural Prediction
        </div>
        <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${conf.border} ${conf.text}`}>
          {annotation.confidence} confidence
        </span>
      </div>

      {/* Predicted structure — the main result */}
      <div>
        <div className={`text-lg font-semibold ${conf.text} leading-snug`}>
          {annotation.predicted_structure}
        </div>
        <div className="text-[11px] text-gray-500 mt-1 font-mono">
          Predicted neutral mass: {annotation.predicted_parent_neutral} Da
        </div>
      </div>

      {/* Aglycone + ladder details */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] text-gray-600 uppercase tracking-widest">Aglycone</span>
          <span className="text-[12px] text-gray-200 font-medium">
            {annotation.aglycone_name ?? "not found"}
          </span>
          {annotation.aglycone_formula && (
            <span className="text-[10px] font-mono text-gray-500">{annotation.aglycone_formula}</span>
          )}
          {annotation.aglycone_ppm != null && (
            <span className="text-[10px] font-mono text-gray-600">{annotation.aglycone_ppm.toFixed(1)} ppm</span>
          )}
        </div>

        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] text-gray-600 uppercase tracking-widest">Sugar units</span>
          <span className="text-[12px] text-gray-200 font-medium">
            {annotation.dominant_loss_count}× {annotation.dominant_loss
              ? annotation.dominant_loss.replace(" loss (−C6H10O5)", "").replace(" loss", "")
              : "—"}
          </span>
          <span className="text-[10px] font-mono text-gray-500">
            {annotation.ladder_length} fragments in ladder
          </span>
        </div>

        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] text-gray-600 uppercase tracking-widest">Aglycone fragment</span>
          <span className="text-[12px] font-mono text-gray-200">{annotation.aglycone_mass} Da</span>
          {annotation.aglycone_source && (
            <span className="text-[10px] text-gray-500">
              via {annotation.aglycone_source}
            </span>
          )}
        </div>
      </div>

      {/* Sequential loss ladder visualization */}
      {annotation.sequential_losses?.length > 0 && (
        <div>
          <div className="text-[10px] text-gray-600 uppercase tracking-widest mb-2">
            Sequential ladder
          </div>
          <div className="flex flex-wrap items-center gap-1 font-mono text-[10px]">
            {annotation.sequential_losses.map((sl, i) => (
              <span key={i} className="flex items-center gap-1">
                <span className="text-gray-300">{sl.to_mass.toFixed(2)}</span>
                <span className={`px-1.5 py-px rounded ${conf.bg} border ${conf.border} ${conf.text}`}>
                  +{sl.loss_da} Da
                </span>
                <span className="text-gray-300">{sl.from_mass.toFixed(2)}</span>
                {i < annotation.sequential_losses.length - 1 && (
                  <span className="text-gray-700 mx-0.5">·</span>
                )}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="text-[10px] text-gray-600 border-t border-gray-800 pt-3">
        Note: this is a computational prediction based on neutral loss pattern matching.
        The exact compound may not be in the database — verify with authentic standards.
      </div>
    </div>
  )
}

function ScoreBar({ pct }) {
  const color = pct === 100
    ? "bg-emerald-500"
    : pct >= 66
    ? "bg-cyan-500"
    : pct >= 33
    ? "bg-yellow-500"
    : "bg-red-500/70"

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-[11px] font-mono font-medium tabular-nums ${
        pct === 100 ? "text-emerald-400" : pct >= 66 ? "text-cyan-400" : pct >= 33 ? "text-yellow-400" : "text-red-400"
      }`}>
        {pct}%
      </span>
    </div>
  )
}

function FragmentBadge({ mass, matched, ppm }) {
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono border
      ${matched
        ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
        : "bg-gray-800 border-gray-700 text-gray-600"}`}
    >
      {matched ? "✓" : "✗"} {(mass ?? 0).toFixed(4)}
      {matched && ppm != null && (
        <span className="text-emerald-600 text-[9px]">{ppm.toFixed(1)}ppm</span>
      )}
    </span>
  )
}

function NeutralLossChain({ losses }) {
  if (!losses?.length) return null

  const lossCount = {}
  for (const l of losses) {
    lossCount[l.loss_name] = (lossCount[l.loss_name] || 0) + 1
  }

  return (
    <div className="mt-3 pt-3 border-t border-gray-800">
      <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-2">
        Neutral losses detected ({losses.length})
      </div>
      <div className="flex flex-wrap gap-1.5 mb-2">
        {Object.entries(lossCount).map(([name, count]) => (
          <span key={name}
                className="px-2 py-0.5 rounded-full text-[10px] font-mono
                           bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
            {name}{count > 1 ? ` ×${count}` : ""}
          </span>
        ))}
      </div>
      <div className="flex flex-col gap-1">
        {losses.map((l, i) => (
          <div key={i} className="flex items-center gap-2 text-[10px] font-mono text-gray-500">
            <span className="text-gray-400">{(l.from_mass ?? 0).toFixed(4)}</span>
            <span className="text-gray-700">→</span>
            <span className="text-gray-400">{(l.to_mass ?? 0).toFixed(4)}</span>
            <span className="px-1.5 py-px rounded bg-gray-800 text-gray-400 border border-gray-700">
              −{l.loss_da ?? 0} Da
            </span>
            <span className="text-cyan-500/70">{l.loss_name}</span>
            <span className="text-gray-700">{(l.ppm_error ?? 0).toFixed(1)} ppm</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function CandidateRow({ candidate, rank, fragments, allLosses }) {
  const [open, setOpen] = useState(rank === 0)

  const fragmentMatches = Array.isArray(candidate.fragment_matches)
    ? candidate.fragment_matches : []

  const matchedSet = new Set(fragmentMatches.map(m => m.fragment_mass))
  const matchMap   = Object.fromEntries(fragmentMatches.map(m => [m.fragment_mass, m.ppm_error]))

  const relevantLosses = allLosses.filter(
    l => matchedSet.has(l.from_mass) || matchedSet.has(l.to_mass)
  )

  const sourceColor = SOURCE_COLORS[candidate.source] || {
    dot: "bg-gray-400", badge: "bg-gray-400/10 text-gray-400 border-gray-400/20"
  }
  const sourceUrl = SOURCE_URLS[candidate.source]?.(candidate.source_id)

  return (
    <div className={`border rounded-xl overflow-hidden transition-all
      ${rank === 0 ? "border-cyan-500/30 bg-cyan-500/5" : "border-gray-800 bg-gray-900/40"}`}
    >
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-white/5 transition-colors"
      >
        <span className="text-[11px] font-mono text-gray-600 w-5 flex-shrink-0">
          #{rank + 1}
        </span>

        <span className={`text-[10px] font-medium px-2 py-0.5 rounded border flex-shrink-0 ${sourceColor.badge}`}>
          {candidate.source}
        </span>

        <div className="flex-1 min-w-0">
          <div className="text-sm text-gray-200 truncate">
            {candidate.name || <span className="text-gray-600 italic">unnamed</span>}
          </div>
          {candidate.formula && (
            <div className="text-[10px] font-mono text-gray-500">{candidate.formula}</div>
          )}
        </div>

        <div className="w-40 flex-shrink-0">
          <div className="text-[10px] text-gray-600 mb-1">
            {candidate.fragments_explained}/{candidate.n_fragments ?? fragments.length} fragments
          </div>
          <ScoreBar pct={Math.round(candidate.coverage_pct ?? 0)} />
        </div>

        <span className="text-[11px] font-mono text-gray-500 w-20 text-right flex-shrink-0">
          {(candidate.avg_ppm ?? 0).toFixed(1)} ppm
        </span>

        <span className={`text-gray-600 transition-transform flex-shrink-0 ${open ? "rotate-180" : ""}`}>
          ▾
        </span>
      </button>

      {open && (
        <div className="px-4 pb-4 border-t border-gray-800/60">
          <div className="mt-3">
            <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-2">
              Fragment coverage
            </div>
            <div className="flex flex-wrap gap-1.5">
              {fragments.map(f => (
                <FragmentBadge
                  key={f}
                  mass={f}
                  matched={matchedSet.has(f)}
                  ppm={matchMap[f]}
                />
              ))}
            </div>
          </div>

          <NeutralLossChain losses={relevantLosses} />

          {sourceUrl && (
            <div className="mt-3 pt-3 border-t border-gray-800">
              <a href={sourceUrl} target="_blank" rel="noreferrer"
                 className="text-[11px] text-cyan-500/70 hover:text-cyan-400 transition-colors font-mono">
                View in {candidate.source} ↗
              </a>
              {candidate.source_id && (
                <span className="text-[10px] text-gray-600 ml-3 font-mono">
                  {candidate.source_id}
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function MS2ResultsTable({ ms2Result }) {
  const [showAllLosses, setShowAllLosses] = useState(false)

  if (!ms2Result) return null

  const fragments         = Array.isArray(ms2Result.fragments)      ? ms2Result.fragments      : []
  const candidates        = Array.isArray(ms2Result.candidates)     ? ms2Result.candidates     : []
  const neutral_losses    = Array.isArray(ms2Result.neutral_losses) ? ms2Result.neutral_losses : []
  const ladder_annotation = ms2Result.ladder_annotation ?? null

  const visibleLosses = showAllLosses ? neutral_losses : neutral_losses.slice(0, 6)

  return (
    <div className="flex flex-col gap-5">

      {/* Summary header */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="text-[11px] font-mono text-gray-500">
          <span className="text-cyan-400 font-medium">{fragments.length}</span> fragments analyzed
        </div>
        <div className="text-[11px] font-mono text-gray-500">
          <span className="text-cyan-400 font-medium">{candidates.length}</span> candidates ranked
        </div>
        {neutral_losses.length > 0 && (
          <div className="text-[11px] font-mono text-gray-500">
            <span className="text-cyan-400 font-medium">{neutral_losses.length}</span> neutral losses detected
          </div>
        )}
      </div>

      {/* ── Structural annotation panel — the main new feature ── */}
      <LadderAnnotationPanel annotation={ladder_annotation} />

      {/* Neutral loss ladder */}
      {neutral_losses.length > 0 && (
        <div className="panel rounded-xl p-4">
          <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-3">
            Spectrum-level neutral loss ladder
          </div>
          <div className="flex flex-col gap-1.5">
            {visibleLosses.map((l, i) => (
              <div key={i} className="flex items-center gap-2 text-[11px] font-mono">
                <span className="text-gray-300 tabular-nums">{(l.from_mass ?? 0).toFixed(4)}</span>
                <span className="text-gray-700">→</span>
                <span className="text-gray-300 tabular-nums">{(l.to_mass ?? 0).toFixed(4)}</span>
                <span className="px-2 py-px rounded bg-gray-800 border border-gray-700 text-gray-400 tabular-nums">
                  −{l.loss_da ?? 0} Da
                </span>
                <span className="text-cyan-400/80">{l.loss_name ?? "unknown"}</span>
                <span className="text-gray-700 text-[10px]">{(l.ppm_error ?? 0).toFixed(1)} ppm</span>
              </div>
            ))}
          </div>
          {neutral_losses.length > 6 && (
            <button
              type="button"
              onClick={() => setShowAllLosses(s => !s)}
              className="mt-2 text-[11px] text-gray-600 hover:text-cyan-400 transition-colors"
            >
              {showAllLosses ? "Show less ↑" : `Show ${neutral_losses.length - 6} more ↓`}
            </button>
          )}
        </div>
      )}

      {/* Ranked candidates */}
      {candidates.length > 0 ? (
        <div className="flex flex-col gap-2">
          <div className="text-[10px] text-gray-600 uppercase tracking-widest">
            Database candidates (direct mass matches only)
          </div>
          {candidates.map((c, i) => (
            <CandidateRow
              key={`${c.source}-${c.source_id}-${i}`}
              candidate={c}
              rank={i}
              fragments={fragments}
              allLosses={neutral_losses}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-gray-600 text-sm">
          No database candidates found for these fragment masses.
        </div>
      )}

    </div>
  )
}