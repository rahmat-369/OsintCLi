#!/usr/bin/env python3
"""Record genuine 40-column Linux PTY interaction against labelled offline fixtures."""
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import struct
import subprocess
import sys
import tempfile
import termios
import time

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from osintcli.core import Config,clean
from osintcli.engine import demo

out=root/'docs/screenshots';out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='osintcli-record-') as temp:
    tmp=Path(temp);config=Config(tmp/'data',tmp/'config');cid=demo(config,3)
    env={**os.environ,'OSINTCLI_DATA_DIR':str(config.data),'OSINTCLI_CONFIG_DIR':str(config.directory),'NO_COLOR':'1','TERM':'xterm-256color','COLUMNS':'40'}
    master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',24,40,0,0))
    process=subprocess.Popen([sys.executable,'-m','osintcli','--width','40','menu'],cwd=root,env=env,stdin=slave,stdout=slave,stderr=slave,start_new_session=True)
    os.close(slave);events=[];start=time.monotonic();transcript='';cursor=0
    # Navigate actual interactive screens; demo seed is deliberately labelled.
    steps=[('Pilih nomor','7\n'),('Case ID','\n'),('1 evidence','1\n'),('Pilih nomor','9\n'),('Case ID','\n'),('Format:','pdf,json\n'),('PDF ringkasan','n\n'),('Folder output',str(tmp/'out')+'\n'),('Pilih nomor','0\n')]
    index=0
    try:
        while process.poll() is None or select.select([master],[],[],0)[0]:
            if time.monotonic()-start>25:raise RuntimeError('Interactive recording timed out')
            if select.select([master],[],[],0.1)[0]:
                try:chunk=os.read(master,65536).decode('utf-8',errors='replace')
                except OSError:break
                if not chunk:break
                events.append([round(time.monotonic()-start,3),'o',chunk]);transcript+=chunk
                if index<len(steps) and steps[index][0] in transcript[cursor:]:
                    # Input delay makes capture readable but does not change output.
                    time.sleep(.15);os.write(master,steps[index][1].encode());cursor=len(transcript);index+=1
        process.wait(timeout=2)
    finally:
        if process.poll() is None:process.kill();process.wait()
        os.close(master)
    if process.returncode or index!=len(steps):raise RuntimeError('Recording did not complete all screens')
    header={'version':2,'width':40,'height':24,'timestamp':int(time.time()),'title':'OSINTCLI actual Linux PTY / OFFLINE FIXTURE','env':{'TERM':'xterm-256color'}}
    (out/'terminal-demo.cast').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in [header,*events])+'\n')
    (out/'terminal-demo.txt').write_text(clean(transcript))
    # Render the actual captured text; no imaginary UI or invented counters.
    from PIL import Image,ImageDraw,ImageFont
    fontfile=Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf')
    if not fontfile.exists():fontfile=root/'osintcli/assets/DejaVuSans.ttf'
    font=ImageFont.truetype(str(fontfile),17);label=ImageFont.truetype(str(fontfile),12)
    frames=[];accum=''
    for _,_,chunk in events:
        accum+=chunk
        if not accum.endswith('> ') and chunk is not events[-1][2]:continue
        lines=clean(accum).replace('\r','').splitlines()[-25:]
        im=Image.new('RGB',(488,650),'#09121b');d=ImageDraw.Draw(im)
        d.text((22,15),'OSINTCLI / ACTUAL LINUX PTY',font=label,fill='#35d18a')
        d.text((22,34),'40 columns | OFFLINE FIXTURE',font=label,fill='#a4b7c4')
        for i,line in enumerate(lines):d.text((22,70+i*22),line,font=font,fill='#d4eef1')
        frames.append(im)
    frames[0].save(out/'terminal-demo.gif',save_all=True,append_images=frames[1:],duration=1600,loop=0,optimize=True)
    frames[0].save(out/'terminal-menu.png')
    print('Recorded',len(events),'output events and',index,'real menu inputs.')
