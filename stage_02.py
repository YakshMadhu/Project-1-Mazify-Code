# Perspective Boxes — Stage 02
# Perspective 3D box rendering
# Reconstructed milestone from the current final program.

import math
import tkinter as tk

SIZE, DEPTH, FOV = 0.7, 6.0, 50
root = tk.Tk(); root.title('Perspective Boxes — Stage 2'); root.geometry('900x600')
canvas = tk.Canvas(root, bg='white', highlightthickness=0); canvas.pack(fill='both', expand=True)

FACES = [
    ([(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1)], '#e7f2ff'),
    ([(-1,-1,-1),(-1,1,-1),(-1,1,1),(-1,-1,1)], '#91b5d8'),
    ([(-1,1,-1),(1,1,-1),(1,1,1),(-1,1,1)], '#c4def4'),
]

def project(x, y, z, cx, cy, f):
    return cx + f*x/z, cy - f*y/z

def redraw(event=None):
    canvas.delete('all')
    w, h = max(1, canvas.winfo_width()), max(1, canvas.winfo_height())
    cx, cy = w/2, h/2
    f = (w/2) / math.tan(math.radians(FOV/2))
    pts = {}
    for x in (-1,1):
        for y in (-1,1):
            for z in (-1,1):
                pts[(x,y,z)] = project(SIZE*x, SIZE*y, DEPTH+SIZE*z, cx, cy, f)
    for corners, color in FACES:
        flat = [v for p in corners for v in pts[p]]
        canvas.create_polygon(*flat, fill=color, outline='#34465c', width=2)
    canvas.create_oval(cx-4, cy-4, cx+4, cy+4, fill='red', outline='')

canvas.bind('<Configure>', redraw)
root.mainloop()
