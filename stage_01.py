# Perspective Boxes — Stage 01
# Basic Tkinter interface
# Reconstructed milestone from the current final program.

import tkinter as tk

root = tk.Tk()
root.title('Perspective Boxes — Stage 1')
root.geometry('900x600')

bar = tk.Frame(root)
bar.pack(fill='x', padx=8, pady=8)

for label, initial in [('Depth', '6'), ('Horizontal %', '0'), ('Vertical %', '0')]:
    tk.Label(bar, text=label).pack(side='left', padx=(8, 2))
    entry = tk.Entry(bar, width=7)
    entry.insert(0, initial)
    entry.pack(side='left')

canvas = tk.Canvas(root, bg='white', highlightthickness=1)
canvas.pack(fill='both', expand=True, padx=8, pady=8)
canvas.create_text(450, 280, text='3D box view will appear here', font=('Arial', 18))

root.mainloop()
