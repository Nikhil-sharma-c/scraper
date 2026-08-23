from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import subprocess, textwrap, json, os

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'video_kit'/'frames'; OUT.mkdir(parents=True,exist_ok=True)
W,H=1920,1080
BG='#080d1c'; PANEL='#111a30'; EDGE='#263457'; INK='#e8edf9'; MUT='#91a0c1'; CY='#22d3ee'; GR='#34d399'; AM='#fbbf24'; RED='#f87171'; PUR='#a78bfa'
segui='C:/Windows/Fonts/segoeui.ttf'; mono='C:/Windows/Fonts/consola.ttf'
def F(size,bold=False,mono_=False): return ImageFont.truetype(mono if mono_ else segui,size)
def box(d,xy,fill=PANEL,outline=EDGE,r=14,w=2): d.rounded_rectangle(xy,radius=r,fill=fill,outline=outline,width=w)
def txt(d,xy,s,size=24,fill=INK,bold=False,mono_=False): d.text(xy,s,font=F(size,bold,mono_),fill=fill)
def wrap(d,x,y,s,width,size=22,fill=MUT,lh=30):
  lines=textwrap.wrap(s,width=width)
  for i,l in enumerate(lines): txt(d,(x,y+i*lh),l,size,fill)
  return y+len(lines)*lh
def base(title,subtitle=''):
 im=Image.new('RGB',(W,H),BG); d=ImageDraw.Draw(im); txt(d,(70,38),'🪐 Scrape-Verse',32,INK,True); txt(d,(370,45),'CONTROL CENTER',18,CY,True)
 txt(d,(70,105),title,38,INK,True)
 if subtitle: txt(d,(70,155),subtitle,20,MUT)
 return im,d
def save(im,n): im.save(OUT/f'{n:02d}.png')

# scene 1 GUI fleet
im,d=base('Your scraping fleet','Every site gets its own card and its own honest health verdict.')
# left form
box(d,(70,225,610,790)); txt(d,(100,255),'NEW SCRAPE',20,CY,True); txt(d,(100,315),'Which website?',22,INK,True); txt(d,(100,350),'Any public page — products, articles, listings…',17,MUT); box(d,(100,385,580,445),BG); txt(d,(120,402),'https://example.com/products',19,MUT)
txt(d,(100,480),'What do you want from it?',22,INK,True); box(d,(100,525,580,630),BG); wrap(d,120,545,'Get the product name, price and rating from every listing',18,18,MUT,25)
box(d,(100,680,580,735),fill='#27cdd0',outline='#27cdd0'); txt(d,(270,695),'Start scraping →',21,'#06121f',True); wrap(d,100,755,'The first run teaches our AI the site. After that, re-runs take seconds.',42,16,MUT,23)
# cards
box(d,(660,225,1850,790)); txt(d,(695,255),'YOUR SCRAPERS',20,CY,True)
cards=[('Hacker News','100%','30 records found','Everything looks good',GR),('onlyflix.to','92%','35 movies found','Some fields need attention',GR),('youtube.com','100%','57 records found','Everything looks good',GR)]
coords=[(700,315,1230,530),(1280,315,1810,530),(700,570,1230,770)]
for (name,score,count,msg,col),(x1,y1,x2,y2) in zip(cards,coords):
 box(d,(x1,y1,x2,y2),BG); txt(d,(x1+22,y1+20),name,23,INK,True); box(d,(x2-145,y1+18,x2-20,y1+52),fill='#123d3b',outline='#123d3b',r=18); txt(d,(x2-130,y1+25),'● Healthy',16,GR,True); txt(d,(x1+22,y1+78),msg,17,MUT); txt(d,(x1+22,y1+120),score,42,col,True); txt(d,(x1+130,y1+140),'health',17,MUT); d.rounded_rectangle((x1+22,y1+180,x2-22,y1+188),4,fill='#203151'); d.rounded_rectangle((x1+22,y1+180,x1+22+(x2-x1-44)*float(score[:-1])/100,y1+188),4,fill=CY); txt(d,(x1+22,y1+202),'📊 '+count,17,MUT); box(d,(x1+22,y2-45,x1+210,y2-12),fill='#123743',outline='#24627a',r=8); txt(d,(x1+72,y2-38),'View data',16,INK,True); box(d,(x1+225,y2-45,x1+410,y2-12),fill=BG,outline=EDGE,r=8); txt(d,(x1+275,y2-38),'↻ Re-run',16,INK,True)
save(im,1)

# scene 2 modal
im,d=base('Real structured output','Onlyflix: filterable data browser — 1 matching row from 35 records.')
# dim background cards
box(d,(70,240,1850,900),fill='#10182b'); txt(d,(110,280),'YOUR SCRAPERS',20,CY,True)
for x,n in [(110,'Hacker News'),(650,'onlyflix.to'),(1190,'youtube.com')]: box(d,(x,350,x+450,520),BG); txt(d,(x+25,380),n,23,INK,True); txt(d,(x+25,430),'100%' if n!='onlyflix.to' else '92%',40,GR,True)
# modal
box(d,(250,300,1670,780),fill='#111a30',outline='#53658f',r=18,w=3); txt(d,(290,335),'onlyflix.to — latest data',27,INK,True); txt(d,(290,375),'“scrape all movie name, rating, cast and release date” · 35 rows',18,MUT)
box(d,(290,425,850,480),BG,outline=CY); txt(d,(315,440),'spider',20,INK); txt(d,(880,443),'1 of 35 rows',17,MUT); box(d,(1390,425,1530,480),BG); txt(d,(1415,441),'Copy JSON',17,INK,True); box(d,(1545,425,1640,480),BG); txt(d,(1562,441),'Download',17,INK,True)
headers=['movie_name','rating','cast','release_date','product_page_url']; xs=[300,610,725,1110,1370]
for x,h in zip(xs,headers): txt(d,(x,520),h,17,MUT,True)
d.rectangle((290,550,1640,555),fill=EDGE); txt(d,(300,580),'Spider-Man: Brand',20,INK); txt(d,(300,612),'New Day',20,INK); txt(d,(610,590),'8.1',20,INK); wrap(d,725,580,'Billy Clements, Eman Esfandi, Florence Pugh, Jacob Batalon, Jon Bernthal',36,17,INK,23); txt(d,(1110,590),'2026-07-31',17,INK); txt(d,(1370,580),'https://onlyflix.to/spider-man-brand-new-day/',15,CY); save(im,2)

# terminal scenes
for idx,title,cmd,filename,accent in [(3,'Silent drift detection','python sv.py demo hn_v2.html','scene3.txt',AM),(4,'Accepted self-healing repair','python sv.py heal --mode "demo:hn_v2.html->hn_v3.html"','scene4.txt',GR),(5,'Safety: reject and rollback','python sv.py heal --mode "demo:hn_v2.html->hn_v4_badrepair.html"','scene5.txt',RED)]:
 im,d=base(title,'Command-line evidence from the same Scrape-Verse pipeline.'); box(d,(90,240,1830,920),fill='#050914',outline=EDGE,r=12); txt(d,(125,275),'C:\\scrape-verse>',22,GR,True,True); txt(d,(450,275),cmd,22,INK,True,True)
 raw=(ROOT/'video_kit'/'assets'/filename).read_text(errors='replace'); lines=raw.splitlines(); y=330
 for line in lines[:24]:
  if len(line)>145: line=line[:142]+'...'
  col=accent if any(w in line for w in ['DRIFT','REJECTED','ACCEPTED','rollback','health','Health','Doctor']) else '#c5d1e8'
  txt(d,(125,y),line,18,col,False,True); y+=25
 txt(d,(125,855),'Scrape-Verse  |  validate → compare → diagnose → heal → re-run → verify',18,MUT,False,True); save(im,idx)

# scene 6 outro
im,d=base('Trust the output, not the promise','Every repair is versioned. Good fixes stay; bad fixes roll back.')
box(d,(150,280,1770,720)); txt(d,(210,325),'REPAIR HISTORY',22,CY,True); cols=[('v',250),('what changed',390),('health',1260),('verdict',1500)]
for h,x in cols: txt(d,(x,390),h,18,MUT,True)
rows=[('v3','scheduled verification heal','100% → 100%','✅ kept',GR),('v2','author at 3%; points at 0%','84.3% → 92%','✅ kept',GR),('v?','bad repair attempt','84.3% → 7.9%','❌ rolled back',RED)]
for i,(a,b,c,e,col) in enumerate(rows):
 y=455+i*72; d.line((210,y-15,1710,y-15),fill=EDGE); txt(d,(250,y),a,19,INK,True); txt(d,(390,y),b,19,INK); txt(d,(1260,y),c,19,INK); txt(d,(1500,y),e,19,col,True)
txt(d,(410,820),'github.com/Nikhil-sharma-c/scraper',32,CY,True); txt(d,(610,885),'Built on Bright Data Scraper Studio',20,MUT); save(im,6)

# Assemble silent 2:30: 25,30,25,25,25,20 seconds
import cv2
out=ROOT/'video_kit'/'scrape-verse-voiceover-ready.mp4'
writer=cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*'mp4v'), 30, (W,H))
for i,sec in enumerate([25,30,25,25,25,20],1):
    frame=cv2.imread(str(OUT/f'{i:02d}.png'))
    for _ in range(sec*30): writer.write(frame)
writer.release()
# Re-encode for broad browser/YouTube compatibility.
tmp=ROOT/'video_kit'/'_voiceover_tmp.mp4'
subprocess.run(['ffmpeg','-y','-i',str(out),'-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(tmp)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
tmp.replace(out)
print(out, out.stat().st_size)
