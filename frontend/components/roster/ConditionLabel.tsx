'use client'
import { useId, useState } from 'react'
import { createPortal } from 'react-dom'
import type { DailySlotCondition } from '@/lib/api'

export default function ConditionLabel({condition,locale,focusable=false}:{condition:DailySlotCondition;locale:'pl'|'en';focusable?:boolean}) {
  const id=useId()
  const [position,setPosition]=useState<{left:number;top:number}|null>(null)
  const retired=condition.condition_type==='active' && condition.operator==='eq' && condition.value===false
  const text=locale==='pl'?condition.label_pl:condition.label_en
  const tip=locale==='pl'
    ? 'Liczymy zawodnika, który przeszedł na trenera, wyłącznie streamuje albo nie grał zawodowo przez ostatnie 12 miesięcy.'
    : 'Counts if the player has moved to coaching, only streams, or has not played professionally in the past 12 months.'
  if(!retired)return <>{text}</>
  const show=(element:HTMLElement)=>{
    const r=element.getBoundingClientRect()
    setPosition({left:Math.max(10,Math.min(r.left,window.innerWidth-290)),top:Math.max(10,Math.min(r.bottom+8,window.innerHeight-94))})
  }
  return <span className="cursor-help underline decoration-dotted underline-offset-4" tabIndex={focusable?0:undefined}
    aria-describedby={position?id:undefined} onMouseEnter={e=>show(e.currentTarget)} onMouseLeave={()=>setPosition(null)}
    onFocus={e=>show(e.currentTarget)} onBlur={()=>setPosition(null)}
    onClick={focusable?e=>{e.stopPropagation();show(e.currentTarget)}:()=>setPosition(null)}
    onKeyDown={e=>{if(e.key==='Escape'&&position){e.stopPropagation();setPosition(null)}}}>
    {text}
    {position&&createPortal(<span role="tooltip" id={id} className="pointer-events-none fixed z-[80] w-[280px] max-w-[calc(100vw-20px)] border bg-white px-3 py-2 text-left text-xs font-normal leading-relaxed shadow-lg"
      style={{left:position.left,top:position.top,color:'var(--text)',borderColor:'var(--line)'}}>{tip}</span>,document.body)}
  </span>
}
