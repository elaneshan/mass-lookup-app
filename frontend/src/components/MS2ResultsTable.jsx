import { useState } from "react"

const SOURCE_URLS = {
  HMDB:      id => `https://hmdb.ca/metabolites/${id}`,
  ChEBI:     id => `https://www.ebi.ac.uk/chebi/searchId.do?chebiId=${id}`,
  LipidMaps: id => `https://www.lipidmaps.org/databases/lmsd/${id}`,
  NPAtlas:   id => `https://www.npatlas.org/explore/compounds/${id}`,
}

const CONFIDENCE_STYLES = {
  high:     { text: "text-emerald-400", border: "border-emerald-500/30", bg: "bg-emerald-500/5",  badge: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" },
  moderate: { text: "text-yellow-400",  border: "border-yellow-500/30",  bg: "bg-yellow-500/5",   badge: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30"   },
  low:      { text: "text-orange-400",  border: "border-orange-500/30",  bg: "bg-orange-500/5",   badge: "bg-orange-500/10 text-orange-400 border-orange-500/30"   },
  none:     { text: "text-gray-500",    border: "border-gray-700",       bg: "bg-gray-900/40",    badge: "bg-gray-800 text-gray-500 border-gray-700"               },
}

function LadderAnnotationPanel({ annotation }) {
  const [showDetails, setShowDetails] = useState(false)
  if (!annotation) return null

  const conf    = CONFIDENCE_STYLES[annotation.confidence] ?? CONFIDENCE_STYLES.none
  const aglyconeUrl = SOURCE_URLS[annotation.aglycone_source]?.(annotation.aglycone_source_id)

  return (
    <div className={`rounded-xl border ${conf.border} ${conf.bg} p-5 flex flex-col gap-4`}>

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="text-[10px] text-gray-500 uppercase tracking-widest">
          Structural Prediction
        </div>
        <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${conf.badge}`}>
          {annotation.confidence} confidence
        </span>
      </div>

      {/* Main prediction */}
      <div>
        <div className={`text-xl font-semibold ${conf.text} leading-snug`}>
          {annotation.predicted_structure}
        </div>
        <div className="text-[11px] text-gray-500 mt-1 font-mono">
          Predicted neutral mass of parent: {annotation.predicted_parent_neutral} Da
        </div>
      </div>

      {/* Key facts grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] text-gray-600 uppercase tracking-widest">Aglycone</span>
          <span className="text-[12px] text-gray-200 font-medium leading-snug">
            {annotation.aglycone_name ?? "not found"}
          </span>
          {annotation.aglycone_formula && (
            <span className="text-[10px] font-mono text-gray-500">{annotation.aglycone_formula}</span>
          )}
          {annotation.aglycone_ppm != null && (
            <span className="text-[10px] font-mono text-gray-600">{annotation.aglycone_ppm.toFixed(1)} ppm</span>
          )}
          {aglyconeUrl && (
            <a href={aglyconeUrl} target="_blank" rel="noreferrer"
               className="text-[10px] text-cyan-500/70 hover:text-cyan-400 transition-colors mt-0.5">
              View in {annotation.aglycone_source} ↗
            </a>
          )}
        </div>

        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] text-gray-600 uppercase tracking-widest">Sugar units</span>
          <span className="text-[12px] text-gray-200 font-medium">
            {annotation.dominant_loss_count}×{" "}
            {annotation.dominant_loss
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
            <span className="text-[10px] text-gray-500">confirmed via {annotation.aglycone_source}</span>
          )}
        </div>
      </div>

      {/* Sequential ladder — collapsible */}
      {annotation.sequential_losses?.length > 0 && (
        <div>
          <button
            type="button"
            onClick={() => setShowDetails(s => !s)}
            className="text-[10px] text-gray-600 hover:text-cyan-400 transition-colors uppercase tracking-widest"
          >
            {showDetails ? "Hide ladder ↑" : "Show sequential ladder ↓"}
          </button>
          {showDetails && (
            <div className="mt-2 flex flex-wrap items-center gap-1 font-mono text-[10px]">
              {annotation.sequential_losses.map((sl, i) => (
                <span key={i} className="flex items-center gap-1">
                  <span className="text-gray-300">{sl.to_mass.toFixed(2)}</span>
                  <span className={`px-1.5 py-px rounded border ${conf.border} ${conf.text} ${conf.bg}`}>
                    +{sl.loss_da} Da
                  </span>
                  <span className="text-gray-300">{sl.from_mass.toFixed(2)}</span>
                  {i < annotation.sequential_losses.length - 1 && (
                    <span className="text-gray-700 mx-0.5">·</span>
                  )}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="text-[10px] text-gray-600 border-t border-gray-800/60 pt-3">
        Computational prediction based on neutral loss pattern matching.
        Verify with authentic standards.
      </div>
    </div>
  )
}

export default function MS2ResultsTable({ ms2Result }) {
  if (!ms2Result) return null

  const fragments         = Array.isArray(ms2Result.fragments)      ? ms2Result.fragments      : []
  const neutral_losses    = Array.isArray(ms2Result.neutral_losses) ? ms2Result.neutral_losses : []
  const ladder_annotation = ms2Result.ladder_annotation ?? null

  return (
    <div className="flex flex-col gap-5">

      {/* Summary */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="text-[11px] font-mono text-gray-500">
          <span className="text-cyan-400 font-medium">{fragments.length}</span> fragments analyzed
        </div>
        {neutral_losses.length > 0 && (
          <div className="text-[11px] font-mono text-gray-500">
            <span className="text-cyan-400 font-medium">{neutral_losses.length}</span> neutral losses detected
          </div>
        )}
      </div>

      {/* Structural annotation — the main result */}
      {ladder_annotation
        ? <LadderAnnotationPanel annotation={ladder_annotation} />
        : (
          <div className="text-center py-16 text-gray-600 text-sm">
            No pattern detected in these fragment masses.
          </div>
        )
      }

    </div>
  )
}