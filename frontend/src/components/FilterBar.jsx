export default function FilterBar({value,onChange}){

return(

<div className="flex items-center gap-2 flex-1">

<input
type="text"
value={value}
onChange={e=>onChange(e.target.value)}
placeholder="filter by name, formula, source, inchikey..."
className="w-full max-w-md
bg-[#0F1720]
border border-gray-700
rounded-lg
px-3 py-1.5
text-[12px]
font-mono
text-gray-300
placeholder-gray-600
focus:outline-none
focus:border-cyan-400
focus:ring-1 focus:ring-cyan-400/20"
/>

{value&&(

<button
onClick={()=>onChange("")}
className="text-xs text-gray-500 hover:text-gray-300"
>
clear
</button>

)}

</div>

)

}