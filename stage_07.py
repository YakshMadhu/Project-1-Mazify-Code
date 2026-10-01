# Perspective Boxes — Stage 07
# Supersampled Pillow rendering
# Reconstructed milestone from the current final program.

import math, time
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk

NEAR,FAR=3.0,12.0; SIZE,FOV,AA=.18,50,4; TURN_SPEED,FINE_TURN=5.0,1.0; DOT_R=7
root=tk.Tk(); root.title('Perspective Boxes'); root.geometry('1100x700')
bar=tk.Frame(root); bar.pack(fill='x'); fields={}
for label,initial in [('Depth','6'),('Horizontal %','0'),('Vertical %','0')]:
    tk.Label(bar,text=label).pack(side='left',padx=(8,2)); e=tk.Entry(bar,width=7); e.insert(0,initial); e.pack(side='left'); fields[label]=e
angle=tk.DoubleVar(value=0); slider=tk.Scale(bar,label='Yaw (added later)',variable=angle,from_=-24,to=24,resolution=.1,orient='horizontal',length=210,state='disabled'); slider.pack(side='left',padx=8)
message=tk.StringVar(value='Create a box.'); tk.Label(root,textvariable=message,anchor='w').pack(fill='x')
body=tk.Frame(root); body.pack(fill='both',expand=True); canvas=tk.Canvas(body,bg='white',highlightthickness=0); canvas.pack(side='left',fill='both',expand=True)
side=tk.Frame(body); side.pack(side='right',fill='y',padx=8); map_canvas=tk.Canvas(side,width=220,height=220,bg='#f2f2f2'); map_canvas.pack()
range_text=tk.StringVar(); tk.Label(side,textvariable=range_text,justify='left',font=('Arial',11,'bold')).pack(fill='x')
rotation_text=tk.StringVar(); tk.Label(side,textvariable=rotation_text,justify='left',font=('Arial',11,'bold')).pack(fill='x',pady=(12,0))
boxes=[]; selected=None; held=set(); last=time.perf_counter(); guide_on=True
FACES=[([(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1)],(0,0,-1),'#e7f2ff'),([(1,-1,1),(-1,-1,1),(-1,1,1),(1,1,1)],(0,0,1),'#d9e5f2'),([(-1,-1,-1),(-1,1,-1),(-1,1,1),(-1,-1,1)],(-1,0,0),'#91b5d8'),([(1,-1,-1),(1,-1,1),(1,1,1),(1,1,-1)],(1,0,0),'#91b5d8'),([(-1,1,-1),(1,1,-1),(1,1,1),(-1,1,1)],(0,1,0),'#c4def4'),([(-1,-1,-1),(-1,-1,1),(1,-1,1),(1,-1,-1)],(0,-1,0),'#aecce8')]

def camera():
    w,h=max(1,canvas.winfo_width()),max(1,canvas.winfo_height()); f=(w/2)/math.tan(math.radians(FOV/2)); return w,h,w/2,h/2,f

def project(p,cx,cy,f): x,y,z=p; return cx+f*x/z,cy-f*y/z

def geometry(pos,yaw,cx,cy,f):
    a=math.radians(yaw); c,s=math.cos(a),math.sin(a); bx,by,bz=pos; verts={}
    for x in (-1,1):
        for y in (-1,1):
            for z in (-1,1): verts[(x,y,z)]=project((bx+SIZE*(x*c+z*s),by+SIZE*y,bz+SIZE*(-x*s+z*c)),cx,cy,f)
    vis=[]
    for corners,n,color in FACES:
        nx,ny,nz=n; nx,nz=nx*c+nz*s,-nx*s+nz*c
        if nx*(bx+SIZE*nx)+ny*(by+SIZE*ny)+nz*(bz+SIZE*nz)<0: vis.append(([verts[v] for v in corners],color,n))
    return vis,verts

def percentages(vis):
    def area(p): return abs(sum(x1*y2-x2*y1 for (x1,y1),(x2,y2) in zip(p,p[1:]+p[:1])))/2
    a={n:area(p) for p,_,n in vis}; front=a.get((0,0,-1),0); left,right=a.get((-1,0,0),0),a.get((1,0,0),0); top,bottom=a.get((0,1,0),0),a.get((0,-1,0),0)
    hs=max(left,right); vs=max(top,bottom); hp=100*hs/(hs+front) if hs+front else 0; vp=100*vs/(vs+front) if vs+front else 0
    return (-hp if right>left else hp,-vp if top>bottom else vp)

def solve(depth,yaw,th,tv):
    w,h,cx,cy,f=camera(); xb=((-cx)*depth/f,(w-cx)*depth/f); yb=((cy-h)*depth/f,cy*depth/f)
    def val(x,y): return percentages(geometry((x,y,depth),yaw,cx,cy,f)[0])
    x=y=0.
    for _ in range(9):
        lo,hi=xb
        for _ in range(24): mid=(lo+hi)/2; lo,hi=(mid,hi) if val(mid,y)[0]<th else (lo,mid)
        x=(lo+hi)/2; lo,hi=yb
        for _ in range(24): mid=(lo+hi)/2; lo,hi=(mid,hi) if val(x,mid)[1]<tv else (lo,mid)
        y=(lo+hi)/2
    ah,av=val(x,y); return (x,y,depth) if abs(ah-th)<.5 and abs(av-tv)<.5 else None

def paint(i):
    box=boxes[i]; w,h,cx,cy,f=camera(); vis,verts=geometry(box['pos'],box['yaw'],cx,cy,f); coords=list(verts.values())
    l=max(0,int(min(x for x,y in coords))-4); t=max(0,int(min(y for x,y in coords))-4); r=min(w,int(max(x for x,y in coords))+5); b=min(h,int(max(y for x,y in coords))+5)
    if r<=l or b<=t: return
    im=Image.new('RGBA',((r-l)*AA,(b-t)*AA)); d=ImageDraw.Draw(im); edge='#8050b5' if i==selected else '#34465c'
    for p,color,_ in vis:
        q=[((x-l)*AA,(y-t)*AA) for x,y in p]; d.polygon(q,fill=color); d.line(q+[q[0]],fill=edge,width=AA*2,joint='curve')
    box['photo']=ImageTk.PhotoImage(im.resize((r-l,b-t),Image.Resampling.LANCZOS)); canvas.itemconfigure(box['image'],image=box['photo']); canvas.coords(box['image'],l,t)
    px,py=project(box['pos'],cx,cy,f); canvas.coords(box['center'],px-3,py-3,px+3,py+3); hp,vp=percentages(vis); canvas.itemconfigure(box['label'],text=f'({hp:+.0f}, {vp:+.0f})'); canvas.coords(box['label'],px,py+14)

def create_box(event=None):
    global selected
    try: depth=float(fields['Depth'].get()); hp=int(fields['Horizontal %'].get()); vp=int(fields['Vertical %'].get())
    except ValueError: message.set('Enter valid values.'); return
    pos=solve(depth,0,hp,vp) if NEAR<=depth<=FAR else None
    if pos is None: message.set('Unavailable placement.'); return
    box={'pos':pos,'yaw':0.,'depth':depth,'photo':None}; box['image']=canvas.create_image(0,0,anchor='nw'); box['center']=canvas.create_oval(0,0,0,0,fill='#8037bf',outline=''); box['label']=canvas.create_text(0,0,fill='#34224a',font=('Arial',10,'bold'))
    old=selected; boxes.append(box); selected=len(boxes)-1
    if old is not None: paint(old)
    paint(selected); update_rotation_range(); guide(); message.set(f'Created Box {selected+1}.')

def inside(px,py,poly):
    hit=False
    for i,(x1,y1) in enumerate(poly):
        x2,y2=poly[(i+1)%len(poly)]
        if (y1>py)!=(y2>py) and px<x1+(py-y1)*(x2-x1)/(y2-y1): hit=not hit
    return hit

def select_box(event):
    global selected
    _,_,cx,cy,f=camera()
    for i in range(len(boxes)-1,-1,-1):
        vis,_=geometry(boxes[i]['pos'],boxes[i]['yaw'],cx,cy,f)
        if any(inside(event.x,event.y,p) for p,_,_ in vis):
            old=selected; selected=i
            if old is not None and old!=i: paint(old)
            paint(i); angle.set(boxes[i]['yaw']); update_rotation_range(); guide(); return

def limit_yaw():
    w,_,_,_,f=camera(); return math.degrees(math.atan(max(0,w/2-DOT_R-1)/f))

def update_rotation_range():
    if selected is None: rotation_text.set('Select a box.'); return
    box=boxes[selected]; _,_,cx,cy,f=camera(); vals=[]
    for i in range(181):
        yaw=-limit_yaw()+2*limit_yaw()*i/180; vals.append(percentages(geometry(box['pos'],yaw,cx,cy,f)[0])[0])
    box['horizontal_range']=(min(vals),max(vals)); cur=percentages(geometry(box['pos'],box['yaw'],cx,cy,f)[0]); rotation_text.set(f'Rotation X: {math.ceil(min(vals)-.49):+d}% to {math.floor(max(vals)+.49):+d}%\nNow: X {cur[0]:+.0f}% Y {cur[1]:+.0f}%')

def guide():
    canvas.delete('guide')
    if selected is None or not guide_on: return
    box=boxes[selected]; _,_,cx,cy,f=camera(); a=math.radians(box['yaw']); bx,by,bz=box['pos']; e=SIZE*2; s,c=math.sin(a),math.cos(a)
    x1,y1=project((bx-e*s,by,bz-e*c),cx,cy,f); x2,y2=project((bx+e*s,by,bz+e*c),cx,cy,f); canvas.create_line(x1,y1,x2,y2,fill='#008e73',width=2,dash=(5,4),tags='guide'); vx=cx+f*math.tan(a); canvas.create_oval(vx-5,cy-5,vx+5,cy+5,outline='#008e73',width=2,tags='guide')

def slider_turn(value):
    if selected is None: return
    boxes[selected]['yaw']=float(value); paint(selected); update_rotation_range(); guide()

def key_down(e):
    if e.keysym in ('Left','Right','Shift_L','Shift_R'): held.add(e.keysym)
def key_up(e): held.discard(e.keysym)
def frame():
    global last
    now=time.perf_counter(); dt=min(now-last,.05); last=now
    if selected is not None:
        turn=int('Left' in held)-int('Right' in held)
        if turn:
            speed=FINE_TURN if ('Shift_L' in held or 'Shift_R' in held) else TURN_SPEED; b=boxes[selected]; b['yaw']=max(-limit_yaw(),min(limit_yaw(),b['yaw']+turn*speed*dt)); angle.set(b['yaw']); paint(selected); update_rotation_range(); guide()
    root.after(8,frame)

def update_map(event=None):
    try: depth=float(fields['Depth'].get())
    except ValueError: return
    if not NEAR<=depth<=FAR: return
    map_canvas.delete('all'); w,h,cx,cy,f=camera(); hs=[]; vs=[]
    for iy in range(24):
        y=(cy-h*iy/23)*depth/f
        for ix in range(32):
            x=(w*ix/31-cx)*depth/f; hp,vp=percentages(geometry((x,y,depth),0,cx,cy,f)[0]); hs.append(hp); vs.append(vp); mx=(hp+100)*219/200; my=(100-vp)*219/200; map_canvas.create_oval(mx-1,my-1,mx+1,my+1,fill='#75b5d6',outline='')
    range_text.set(f'At depth {depth:g}:\nX {math.floor(min(hs)):+d}% to {math.ceil(max(hs)):+d}%\nY {math.floor(min(vs)):+d}% to {math.ceil(max(vs)):+d}%')

def show_instructions():
    win=tk.Toplevel(root); win.title('Instructions'); text=tk.Text(win,wrap='word',width=70,height=25); text.pack(fill='both',expand=True)
    text.insert('1.0','TO CREATE A BOX\\nChoose a depth from 3 to 12, then horizontal and vertical percentages.\\n\\nWHAT THE PERCENTAGES MEAN\\nPositive horizontal = left face visible. Negative horizontal = right face visible. Positive vertical = bottom visible. Negative vertical = top visible.\\n\\nSELECT AND ROTATE\\nClick a box, then use Left/Right or the yaw slider. The box center and depth remain fixed.'); text.configure(state='disabled')

tk.Button(bar,text='Create box',command=create_box).pack(side='left',padx=8); slider.configure(command=slider_turn)
root.bind('<Return>',create_box)
for e in fields.values(): e.bind('<KeyRelease>',update_map)
root.after(200,update_map)
