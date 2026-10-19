import re
UP='A-ZΑ-Ω'; LOW='a-zα-ω0-9∞'
SUB=re.compile(r'(?<=[^\s_(])_(\{[^}]*\}|\([^)]*\)|['+UP+r']+['+LOW+r']*(?:,['+LOW+UP+r']+)*|['+LOW+r']+(?:,['+LOW+UP+r']+)*)')
SUP=re.compile(r'(?<=\S)\^(\{[^}]*\}|\([^)]*\)|[−\-]?[A-Za-z0-9.]+)')
def fix_text(inner,size):
    if '<' in inner.replace('&lt;','').replace('&gt;',''): return inner
    d=max(3,round(size*0.28))
    toks=[];pos=0
    pat=re.compile(SUB.pattern+'|'+SUP.pattern)
    for m in pat.finditer(inner):
        toks.append(('n',inner[pos:m.start()]))
        if m.group(1) is not None: toks.append(('sub',m.group(1)))
        else: toks.append(('sup',m.group(2)))
        pos=m.end()
    if not toks: return inner
    toks.append(('n',inner[pos:]))
    out='';shift=0
    for k,t in toks:
        if k=='n':
            if shift: out+=f'<tspan dy="{-shift}">{t}</tspan>';shift=0
            else: out+=t
        else:
            t=t[1:-1] if t[:1] in '({' else t
            dy=d if k=='sub' else -round(size*0.38)
            if shift: dy-=shift
            out+=f'<tspan dy="{dy}" font-size="{round(size*0.74)}">{t}</tspan>'; shift=(d if k=='sub' else -round(size*0.38))
    if shift: out+=f'<tspan dy="{-shift}"></tspan>'
    return out
def fix_svg(svg):
    def rep(m):
        tag,inner=m.group(1),m.group(2)
        fs=re.search(r'font-size="([\d.]+)"',tag); size=float(fs.group(1)) if fs else 14
        return tag+fix_text(inner,size)+'</text>'
    return re.sub(r'(<text[^>]*>)(.*?)</text>',rep,svg,flags=re.S)
if __name__=='__main__':
    for s in ['T_SL/W_TO','P_max &lt; P_cr','C_L,max stall','D = qSC_D0 + W²/(qπeb²)','T^(3/2) x','Cauchy point p_C','x_P = 1.2']:
        print(fix_text(s,14))
