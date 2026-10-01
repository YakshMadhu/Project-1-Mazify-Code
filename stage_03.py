# Perspective Boxes — Stage 03
# Visible face percentage calculation
# Reconstructed milestone from the current final program.

import math
import tkinter as tk

SIZE, DEPTH, FOV = 0.7, 6.0, 50
root = tk.Tk(); root.title('Perspective Boxes — Stage 3'); root.geometry('900x600')
canvas = tk.Canvas(root, bg='white', highlightthickness=0); canvas.pack(fill='both', expand=True)
status = tk.StringVar(); tk.Label(root, textvariable=status, font=('Arial', 12, 'bold')).pack(fill='x')

FACES = [
    ([(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1)], (0,0,-1), '#e7f2ff'),
    ([(-1,-1,-1),(-1,1,-1),(-1,1,1),(-1,-1,1)], (-1,0,0), '#91b5d8'),
    ([(1,-1,-1),(1,-1,1),(1,1,1),(1,1,-1)], (1,0,0), '#91b5d8'),
    ([(-1,1,-1),(1,1,-1),(1,1,1),(-1,1,1)], (0,1,0), '#c4def4'),
    ([(-1,-1,-1),(-1,-1,1),(1,-1,1),(1,-1,-1)], (0,-1,0), '#aecce8'),
]

def area(poly):
    return abs(sum(x1*y2-x2*y1 for (x1,y1),(x2,y2) in zip(poly, poly[1:]+poly[:1])))/2

def redraw(event=None):
    canvas.delete('all')
    w,h=max(1,canvas.winfo_width()),max(1,canvas.winfo_height()); cx,cy=w/2,h/2
    f=(w/2)/math.tan(math.radians(FOV/2))
    bx,by=1.0,-0.7
    def proj(p):
        x,y,z=p; return cx+f*x/z, cy-f*y/z
    pts={(x,y,z):proj((bx+SIZE*x,by+SIZE*y,DEPTH+SIZE*z)) for x in (-1,1) for y in (-1,1) for z in (-1,1)}
    areas={}
    for corners, normal, color in FACES:
        poly=[pts[v] for v in corners]
        canvas.create_polygon(*[v for p in poly for v in p],fill=color,outline='#34465c',width=2)
        areas[normal]=area(poly)
    front=areas.get((0,0,-1),0); left=areas.get((-1,0,0),0); right=areas.get((1,0,0),0)
    top=areas.get((0,1,0),0); bottom=areas.get((0,-1,0),0)
    side=max(left,right); vert=max(top,bottom)
    hp=100*side/(side+front) if side+front else 0
    vp=100*vert/(vert+front) if vert+front else 0
    hp=-hp if right>left else hp; vp=-vp if top>bottom else vp
    status.set(f'Visible-face percentages: horizontal {hp:+.0f}%, vertical {vp:+.0f}%')

canvas.bind('<Configure>', redraw)
root.mainloop()
