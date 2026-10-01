# Perspective Boxes — Stage 05
# Valid percentage map and placement validation
# Reconstructed milestone from the current final program.

import math
import tkinter as tk

NEAR,FAR=3.0,12.0
SIZE,FOV=0.18,50
root=tk.Tk(); root.title('Perspective Boxes — Stage 4'); root.geometry('1100x650')
bar=tk.Frame(root); bar.pack(fill='x')
fields={}
for label,initial in [('Depth','6'),('Horizontal %','0'),('Vertical %','0')]:
    tk.Label(bar,text=label).pack(side='left',padx=(8,2)); e=tk.Entry(bar,width=7); e.insert(0,initial); e.pack(side='left'); fields[label]=e
message=tk.StringVar(value='Choose depth and percentages.'); tk.Label(root,textvariable=message,anchor='w').pack(fill='x')
body=tk.Frame(root); body.pack(fill='both',expand=True)
canvas=tk.Canvas(body,bg='white',highlightthickness=0); canvas.pack(side='left',fill='both',expand=True)
side=tk.Frame(body); side.pack(side='right',fill='y',padx=8)
map_canvas=tk.Canvas(side,width=220,height=220,bg='#f2f2f2'); map_canvas.pack()
FACES=[
([(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1)],(0,0,-1),'#e7f2ff'),
([(-1,-1,-1),(-1,1,-1),(-1,1,1),(-1,-1,1)],(-1,0,0),'#91b5d8'),
([(1,-1,-1),(1,-1,1),(1,1,1),(1,1,-1)],(1,0,0),'#91b5d8'),
([(-1,1,-1),(1,1,-1),(1,1,1),(-1,1,1)],(0,1,0),'#c4def4'),
([(-1,-1,-1),(-1,-1,1),(1,-1,1),(1,-1,-1)],(0,-1,0),'#aecce8')]

def camera():
    w,h=max(1,canvas.winfo_width()),max(1,canvas.winfo_height()); f=(w/2)/math.tan(math.radians(FOV/2)); return w,h,w/2,h/2,f

def project(p,cx,cy,f): x,y,z=p; return cx+f*x/z,cy-f*y/z

def geometry(pos,yaw,cx,cy,f):
    a=math.radians(yaw); c,s=math.cos(a),math.sin(a); bx,by,bz=pos; verts={}
    for x in (-1,1):
        for y in (-1,1):
            for z in (-1,1): verts[(x,y,z)]=project((bx+SIZE*(x*c+z*s),by+SIZE*y,bz+SIZE*(-x*s+z*c)),cx,cy,f)
    visible=[]
    for corners,normal,color in FACES:
        nx,ny,nz=normal; nx,nz=nx*c+nz*s,-nx*s+nz*c
        if nx*(bx+SIZE*nx)+ny*(by+SIZE*ny)+nz*(bz+SIZE*nz)<0: visible.append(([verts[v] for v in corners],color,normal))
    return visible,verts

def percentages(visible):
    def area(p): return abs(sum(x1*y2-x2*y1 for (x1,y1),(x2,y2) in zip(p,p[1:]+p[:1])))/2
    a={n:area(p) for p,_,n in visible}; front=a.get((0,0,-1),0); left,right=a.get((-1,0,0),0),a.get((1,0,0),0); top,bottom=a.get((0,1,0),0),a.get((0,-1,0),0)
    side,vert=max(left,right),max(top,bottom); hp=100*side/(side+front) if side+front else 0; vp=100*vert/(vert+front) if vert+front else 0
    return (-hp if right>left else hp,-vp if top>bottom else vp)

def solve(depth,yaw,target_h,target_v):
    w,h,cx,cy,f=camera(); xb=((-cx)*depth/f,(w-cx)*depth/f); yb=((cy-h)*depth/f,cy*depth/f)
    def value(x,y): return percentages(geometry((x,y,depth),yaw,cx,cy,f)[0])
    x=y=0.0
    for _ in range(9):
        lo,hi=xb
        for _ in range(26):
            mid=(lo+hi)/2
            if value(mid,y)[0]<target_h: lo=mid
            else: hi=mid
        x=(lo+hi)/2; lo,hi=yb
        for _ in range(26):
            mid=(lo+hi)/2
            if value(x,mid)[1]<target_v: lo=mid
            else: hi=mid
        y=(lo+hi)/2
    actual=value(x,y)
    return (x,y,depth) if abs(actual[0]-target_h)<.5 and abs(actual[1]-target_v)<.5 else None

def create_box(event=None):
    try: depth=float(fields['Depth'].get()); hp=int(fields['Horizontal %'].get()); vp=int(fields['Vertical %'].get())
    except ValueError: message.set('Enter valid numbers.'); return
    if not (NEAR<=depth<=FAR and -100<=hp<=100 and -100<=vp<=100): message.set('Depth 3–12; percentages -100 to +100.'); return
    pos=solve(depth,0,hp,vp)
    if pos is None: message.set('That percentage pair is not available at this depth.'); return
    canvas.delete('box'); w,h,cx,cy,f=camera(); visible,_=geometry(pos,0,cx,cy,f)
    for poly,color,_ in visible: canvas.create_polygon(*[v for p in poly for v in p],fill=color,outline='#34465c',width=2,tags='box')
    message.set(f'Placed box at ({hp:+d}, {vp:+d}), depth {depth:g}.')

def update_map(event=None):
    try: depth=float(fields['Depth'].get())
    except ValueError: return
    if not NEAR<=depth<=FAR: return
    map_canvas.delete('all'); w,h,cx,cy,f=camera()
    for iy in range(28):
        py=h*iy/27; y=(cy-py)*depth/f
        for ix in range(36):
            px=w*ix/35; x=(px-cx)*depth/f
            hp,vp=percentages(geometry((x,y,depth),0,cx,cy,f)[0]); mx=(hp+100)*219/200; my=(100-vp)*219/200
            map_canvas.create_oval(mx-1,my-1,mx+1,my+1,fill='#75b5d6',outline='')
    map_canvas.create_line(110,0,110,220,fill='#888'); map_canvas.create_line(0,110,220,110,fill='#888')

def create_and_refresh(event=None): create_box(); update_map()
tk.Button(bar,text='Create box',command=create_and_refresh).pack(side='left',padx=8)
for e in fields.values(): e.bind('<KeyRelease>',update_map)
root.after(200,update_map)
root.bind('<Return>',create_and_refresh)
root.mainloop()
