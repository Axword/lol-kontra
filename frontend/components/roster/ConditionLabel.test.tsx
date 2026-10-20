import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import ConditionLabel from './ConditionLabel'
const retired={id:1,condition_type:'active',operator:'eq',value:false,label_pl:'Zakończył karierę',label_en:'Retired'}
afterEach(cleanup)
describe('Retired explanation',()=>{
  it.each(['pl','en'] as const)('shows the coaching, streaming and year rule on hover in %s',locale=>{
    render(<ConditionLabel condition={retired} locale={locale} focusable />)
    const label=screen.getByText(locale==='pl'?retired.label_pl:retired.label_en)
    expect(screen.queryByRole('tooltip')).toBeNull()
    fireEvent.mouseEnter(label)
    expect(screen.getByRole('tooltip').textContent).toMatch(locale==='pl'?/trenera.*streamuje.*12 miesięcy/:/coaching.*streams.*12 months/)
    fireEvent.mouseLeave(label)
    expect(screen.queryByRole('tooltip')).toBeNull()
    fireEvent.focus(label)
    expect(screen.getByRole('tooltip')).toBeTruthy()
    fireEvent.keyDown(label,{key:'Escape'})
    expect(screen.queryByRole('tooltip')).toBeNull()
    fireEvent.click(label)
    expect(screen.getByRole('tooltip')).toBeTruthy()
  })
  it('does not attach the retirement tooltip to an active-player clue',()=>{
    render(<ConditionLabel condition={{...retired,value:true,label_en:'Still active'}} locale="en" />)
    fireEvent.mouseEnter(screen.getByText('Still active'))
    expect(screen.queryByRole('tooltip')).toBeNull()
  })
})
