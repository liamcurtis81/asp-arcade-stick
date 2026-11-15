#!/usr/bin/env python3
"""command.dat move lists -> 1200x900 page images for the in-game viewer.
usage: render_moves.py moves_card.json outdir"""
import json, re, sys, os
from PIL import Image, ImageDraw, ImageFont
FB = '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf'
FR = '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf'
FS = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
W, H, M = 1200, 900, 36
SZ = 27
fb, fr, fsym = ImageFont.truetype(FB, SZ), ImageFont.truetype(FR, SZ), ImageFont.truetype(FS, SZ)
ftitle = ImageFont.truetype(FB, 40); fsmall = ImageFont.truetype(FB, 17); fhead = ImageFont.truetype(FB, 25)
BG, FG, DIM, HEAD = (24, 26, 38), (235, 235, 235), (150, 155, 175), (255, 196, 60)
ARW = {'1':'↙','2':'↓','3':'↘','4':'←','5':'●','6':'→','7':'↖','8':'↑','9':'↗'}
MOT = {'t':'↓↘→','p':'↓↙←','m':'←↙↓↘→','k':'→↘↓↙←','o':'→↘↓','q':'←↖↑','r':'↑↗→','s':'←↙↓',
       'u':'→↗↑','v':'↑↖←','l':'←↖↑↗→','n':'→↗↑↖←','w':'360','x':'360','y':'360','z':'360',
       'L':'→→','M':'←←','Q':'720','R':'720'}
# button chips: label, fill
NEO = {'A':((214,48,49),'A'),'B':((240,190,30),'B'),'C':((46,170,80),'C'),'D':((40,110,220),'D')}
BTN = {'P':'P','K':'K','G':'G','S':'START','H':'H','Z':'Z'}
EXP = {'E':'LP','F':'MP','G':'HP','H':'LK','I':'MK','J':'HK','T':'3K','U':'3P','V':'2K','W':'2P','s':'S','S':'SEL'}
WORD = {'^':'AIR','?':'DIR','X':'TAP','|':'JUMP','O':'HOLD','-':'(air)','=':'(crouch)','~':'CHARGE'}
EWORD = {'-':'(close)','=':'(far)','*':'TAP!','?':'ANY','M':'MAX'}
SYM = {'+':'+','.':'…','!':'→','`':'·','@':'◎','(':'●',')':'○','*':'☆','&':'★','%':'△','$':'▲','#':'▣',']':'□','[':'■','{':'▽','}':'▼','<':'◇','>':'◆'}
ESYM = {'!':'⇒'}

def tokens(s):
    """Split a line into ('t',text) and visual tokens."""
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c in '_^' and i + 1 < len(s):
            k = s[i+1]; i += 2
            if c == '_':
                if k in ARW: out.append(('arw', ARW[k]))
                elif k in MOT: out.append(('mot', MOT[k]))
                elif k in NEO: out.append(('neo', k))
                elif k in 'abcdefghij': out.append(('chip', str('abcdefghij'.index(k)+1)))
                elif k in BTN: out.append(('chip', BTN[k]))
                elif k in WORD: out.append(('word', WORD[k]))
                elif k in SYM: out.append(('sym', SYM[k]))
                else: out.append(('t', k))
            else:
                if k in ARW: out.append(('hold', ARW[k]))
                elif k in EXP: out.append(('chip', EXP[k]))
                elif k in EWORD: out.append(('word', EWORD[k]))
                elif k in ESYM: out.append(('sym', ESYM[k]))
                else: out.append(('t', k))
        else:
            j = i
            while j < len(s) and s[j] not in '_^': j += 1
            out.append(('t', s[i:j])); i = j
    return out

def tok_w(d, t, v):
    if t == 't': return d.textlength(v, font=fr)
    if t in ('arw', 'mot', 'hold', 'sym'): return d.textlength(v, font=fsym) + 2
    if t == 'neo': return SZ + 4
    if t == 'chip': return max(SZ, d.textlength(v, font=fsmall) + 14) + 4
    if t == 'word': return d.textlength(v, font=fsmall) + 12
    return 0

def draw_tok(d, x, y, t, v):
    if t == 't': d.text((x, y), v, font=fr, fill=FG)
    elif t in ('arw', 'mot', 'sym'): d.text((x, y), v, font=fsym, fill=(120, 200, 255))
    elif t == 'hold':
        d.text((x, y), v, font=fsym, fill=(255, 210, 90))
        w = d.textlength(v, font=fsym); d.line((x, y + SZ + 2, x + w, y + SZ + 2), fill=(255, 210, 90), width=3)
    elif t == 'neo':
        col = NEO[v][0]; d.ellipse((x + 1, y + 3, x + SZ + 1, y + SZ + 3), fill=col)
        d.text((x + SZ/2 + 1, y + SZ/2 + 3), v, font=fsmall, fill=(255, 255, 255) if v != 'B' else (40, 30, 0), anchor='mm')
    elif t == 'chip':
        w = max(SZ, d.textlength(v, font=fsmall) + 14)
        d.rounded_rectangle((x + 1, y + 3, x + w + 1, y + SZ + 3), radius=SZ//2, fill=(90, 96, 120))
        d.text((x + w/2 + 1, y + SZ/2 + 3), v, font=fsmall, fill=(255, 255, 255), anchor='mm')
    elif t == 'word':
        w = d.textlength(v, font=fsmall) + 10
        d.rounded_rectangle((x + 1, y + 5, x + w + 1, y + SZ + 1), radius=4, outline=(170, 175, 200), width=2)
        d.text((x + w/2 + 1, y + SZ/2 + 3), v, font=fsmall, fill=(200, 205, 225), anchor='mm')

def parse(body):
    blocks = re.findall(r'\$cmd\n(.*?)\n\$end', body, flags=re.S)
    out = []
    for b in blocks:
        lines = [l.rstrip() for l in b.split('\n')]
        if not lines: continue
        title = lines[0].replace('Â«', '').replace('Â»', '').replace('«', '').replace('»', '').strip()
        rest = [l for l in lines[1:] if not re.fullmatch(r'-{5,}', l.strip())]
        out.append((title, rest))
    return out

def render_game(key, body, outdir):
    blocks = parse(body)
    info = blocks[0][1] if blocks and 'INFO' in blocks[0][0] else []
    gname = info[0].strip() if info else key
    pages = []
    cur = None
    y = 0
    def newpage(title):
        im = Image.new('RGB', (W, H), BG); d = ImageDraw.Draw(im)
        d.text((M, 22), title, font=ftitle, fill=HEAD)
        d.text((W - M, 34), gname, font=fsmall, fill=DIM, anchor='ra')
        d.line((M, 78, W - M, 78), fill=(70, 74, 95), width=2)
        return im, d
    for title, lines in blocks:
        if 'INFO' in title: continue
        im, d = newpage(title); y = 96; part = 1
        for ln in lines:
            if not ln.strip():
                y += SZ // 2; continue
            if y > H - M - SZ:
                pages.append(im); part += 1
                im, d = newpage(title + ' (cont.)'); y = 96
            m = re.fullmatch(r'\s*:(.*):\s*', ln)
            if m:
                d.text((M, y), m.group(1), font=fhead, fill=HEAD); y += SZ + 10; continue
            # name ... command: split on 2+ spaces
            parts = re.split(r'\s{2,}', ln.strip(), maxsplit=1)
            indent = (len(ln) - len(ln.lstrip())) * 6
            if len(parts) == 2:
                name, cmd = parts
                nx = M + indent
                for t, v in tokens(name):
                    if t == 't':
                        d.text((nx, y), v, font=fb, fill=FG); nx += d.textlength(v, font=fb)
                    else:
                        draw_tok(d, nx, y, t, v); nx += tok_w(d, t, v)
                toks = tokens(cmd)
                tw = sum(tok_w(d, t, v) for t, v in toks)
                x = max(W - M - tw, nx + 20)
                if x + tw > W - M:  # command on its own line
                    y += SZ + 8; x = max(M + 40, W - M - tw)
                for t, v in toks:
                    draw_tok(d, x, y, t, v); x += tok_w(d, t, v)
            else:
                x = M + indent
                for t, v in tokens(ln.strip()):
                    if x + tok_w(d, t, v) > W - M: y += SZ + 8; x = M + indent + 20
                    draw_tok(d, x, y, t, v); x += tok_w(d, t, v)
            y += SZ + 10
        pages.append(im)
    os.makedirs(os.path.join(outdir, key), exist_ok=True)
    for i, p in enumerate(pages, 1):
        p.save(os.path.join(outdir, key, '%03d.jpg' % i), quality=88)
    return len(pages)

if __name__ == '__main__':
    data = json.load(open(sys.argv[1]))
    only = sys.argv[3:] or sorted(data)
    for k in only:
        print(k, render_game(k, data[k], sys.argv[2]))
