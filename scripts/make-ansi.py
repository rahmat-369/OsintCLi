#!/usr/bin/env python3
"""Generate the original vector emblem, PNG master and ANSI variants; no network."""
from pathlib import Path
from PIL import Image, ImageDraw
import argparse
p=argparse.ArgumentParser();p.add_argument('--out',default=str(Path(__file__).resolve().parents[1]/'osintcli/assets'));args=p.parse_args()
out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
svg='''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"><rect width="256" height="256" fill="#09121b"/><g fill="none" stroke="#00c6d7" stroke-width="12"><circle cx="108" cy="104" r="72"/><ellipse cx="108" cy="104" rx="34" ry="72"/><path d="M36 104h144M48 66h120M48 142h120"/></g><circle cx="158" cy="158" r="37" fill="#09121b" stroke="#35d18a" stroke-width="14"/><path d="m185 185 40 40" stroke="#35d18a" stroke-width="20" stroke-linecap="round"/></svg>'''
(out/'icon-source.svg').write_text(svg)
im=Image.new('RGB',(256,256),'#09121b');d=ImageDraw.Draw(im)
d.ellipse((36,32,180,176),outline='#00c6d7',width=12);d.ellipse((74,32,142,176),outline='#00c6d7',width=12)
for y,x1,x2 in [(104,36,180),(66,48,168),(142,48,168)]:d.line((x1,y,x2,y),fill='#00c6d7',width=12)
d.ellipse((121,121,195,195),fill='#09121b',outline='#35d18a',width=14);d.line((185,185,225,225),fill='#35d18a',width=20)
im.save(out/'icon-source.png')
for width in [24,28,32]:
 small=im.resize((width,width),Image.Resampling.LANCZOS)
 for mode in ['rgb','256']:
  lines=[]
  for y in range(0,width,2):
   line=''
   for x in range(width):
    a=small.getpixel((x,y));b=small.getpixel((x,y+1))
    def color(c,bg=False):
     if mode=='rgb':return f'\x1b[{48 if bg else 38};2;{c[0]};{c[1]};{c[2]}m'
     index=16+36*round(c[0]/255*5)+6*round(c[1]/255*5)+round(c[2]/255*5)
     return f'\x1b[{48 if bg else 38};5;{index}m'
    line+=color(a)+color(b,True)+'▀'
   lines.append(line+'\x1b[0m')
  text='\n'.join(lines)+'\n';(out/f'icon-{width}-{mode}.ans').write_text(text)
  if width==24:(out/('icon-rgb.ans' if mode=='rgb' else 'icon-mobile.ans')).write_text(text)
(out/'icon-mobile.txt').write_text('    .-------.\n   /  | | |  \\\n  |---|-+-|---|\n   \\  | | /==\\\n    `-----|  |\n           \\==\\_\n               \\\n')
print('Generated original globe/lens icon and 24/28/32 column ANSI variants.')
