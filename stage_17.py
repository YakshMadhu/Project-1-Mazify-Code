# Perspective Boxes — Stage 17
# Current final program with continuous offline Faster-Whisper recognition
# Reconstructed milestone from the current final program.

import math

import re

import hashlib

import time

import threading

import queue

import tkinter as tk

try:

    import speech_recognition as sr

except ImportError:

    sr = None

from PIL import Image, ImageDraw, ImageTk

NEAR, FAR = 3.0, 12.0

SIZE, FOV, AA = 0.18, 50, 4

TURN_SPEED, FINE_TURN = 5.0, 1.0

CENTER_R, DOT_R = 4, 7

MAP_SIZE = 220

root = tk.Tk()

root.title('Perspective boxes — valid face percentages')

root.geometry('1100x740')

bar = tk.Frame(root)

bar.pack(fill='x')

fields = {}

for label, initial in [('Depth', '6'), ('Horizontal %', '0'), ('Vertical %', '0')]:

    tk.Label(bar, text=label).pack(side='left', padx=(8, 2))

    entry = tk.Entry(bar, width=7)

    entry.insert(0, initial)

    entry.pack(side='left')

    fields[label] = entry

angle_var = tk.DoubleVar(value=0)

yaw_control = tk.Scale(

    bar, label='Yaw', variable=angle_var, from_=-24, to=24,

    resolution=0.1, orient='horizontal', length=210

)

yaw_control.pack(side='left', padx=8)

message = tk.StringVar(value='Choose depth and percentages, then create a box.')

tk.Label(root, textvariable=message, anchor='w').pack(fill='x')

voice_status = tk.StringVar(value='Voice control: starting...')

tk.Label(root, textvariable=voice_status, anchor='w').pack(fill='x')

voice_events = queue.Queue()

voice_echo_ignore_until = 0.0

voice_flow = {

    'phase': None,

    'depth': None,

    'horizontal': None,

    'horizontal_min': 0,

    'horizontal_max': 0,

    'vertical_min': 0,

    'vertical_max': 0,

    'rotation_box': None,

    'rotation_min': 0,

    'rotation_max': 0,

}

body = tk.Frame(root)

body.pack(fill='both', expand=True)

canvas = tk.Canvas(body, bg='white', highlightthickness=0)

canvas.pack(side='left', fill='both', expand=True)

side = tk.Frame(body)

side.pack(side='right', fill='y', padx=8)

tk.Label(side, text='Valid (horizontal, vertical) pairs').pack()

map_canvas = tk.Canvas(

    side, width=MAP_SIZE, height=MAP_SIZE,

    bg='#f2f2f2', highlightthickness=1

)

map_canvas.pack()

tk.Label(side, text='+X left / −X right\n+Y bottom / −Y top').pack()

range_text = tk.StringVar(value='Choose a depth to see the ranges.')

tk.Label(

    side, textvariable=range_text, justify='left', anchor='w',

    font=('Arial', 11, 'bold')

).pack(fill='x', pady=(12, 0))

rotation_text = tk.StringVar(value='Place a box to see its rotation range.')

tk.Label(

    side, textvariable=rotation_text, justify='left', anchor='w',

    font=('Arial', 11, 'bold')

).pack(fill='x', pady=(12, 0))

boxes, held, releases = [], set(), {}

selected = None

guide_on = True

last_time = time.perf_counter()

map_job = None

syncing_yaw = False

yaw_control.configure(state='disabled')

# Corners, outward normal, color.

FACES = [

    ([(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1)],(0,0,-1),'#e7f2ff'),

    ([(1,-1,1),(-1,-1,1),(-1,1,1),(1,1,1)],(0,0,1),'#d9e5f2'),

    ([(-1,-1,-1),(-1,1,-1),(-1,1,1),(-1,-1,1)],(-1,0,0),'#91b5d8'),

    ([(1,-1,-1),(1,-1,1),(1,1,1),(1,1,-1)],(1,0,0),'#91b5d8'),

    ([(-1,1,-1),(1,1,-1),(1,1,1),(-1,1,1)],(0,1,0),'#c4def4'),

    ([(-1,-1,-1),(-1,-1,1),(1,-1,1),(1,-1,-1)],(0,-1,0),'#aecce8'),

]

def camera():

    w, h = max(1, canvas.winfo_width()), max(1, canvas.winfo_height())

    f = (w/2)/math.tan(math.radians(FOV/2))

    return w, h, w/2, h/2, f

def limit_yaw():

    w, _, _, _, f = camera()

    return math.degrees(math.atan(max(0, w/2-DOT_R-1)/f))

def project(p, cx, cy, f):

    x, y, z = p

    return cx+f*x/z, cy-f*y/z

def geometry(pos, yaw, cx, cy, f):

    a = math.radians(yaw)

    c, s = math.cos(a), math.sin(a)

    bx, by, bz = pos

    vertices = {}

    for x in (-1, 1):

        for y in (-1, 1):

            for z in (-1, 1):

                vertices[(x,y,z)] = project(

                    (bx+SIZE*(x*c+z*s), by+SIZE*y,

                     bz+SIZE*(-x*s+z*c)), cx, cy, f

                )

    visible = []

    for corners, normal, color in FACES:

        nx, ny, nz = normal

        nx, nz = nx*c+nz*s, -nx*s+nz*c

        if nx*(bx+SIZE*nx)+ny*(by+SIZE*ny)+nz*(bz+SIZE*nz) < 0:

            visible.append(([vertices[v] for v in corners], color, normal))

    return visible, vertices

def percentages(visible):

    def area(p):

        return abs(sum(

            x1*y2-x2*y1 for (x1,y1),(x2,y2)

            in zip(p,p[1:]+p[:1])

        ))/2

    a = {normal: area(p) for p, _, normal in visible}

    front = a.get((0,0,-1), 0)

    left, right = a.get((-1,0,0),0), a.get((1,0,0),0)

    top, bottom = a.get((0,1,0),0), a.get((0,-1,0),0)

    side, vertical = max(left,right), max(top,bottom)

    h = 100*side/(side+front) if side+front else 0

    v = 100*vertical/(vertical+front) if vertical+front else 0

    return (-h if right>left else h, -v if top>bottom else v)

def solve(depth, yaw, target_h, target_v):

    w, h, cx, cy, f = camera()

    xb = ((CENTER_R-cx)*depth/f, (w-CENTER_R-cx)*depth/f)

    yb = ((cy-h+CENTER_R)*depth/f, (cy-CENTER_R)*depth/f)

    def value(x, y):

        return percentages(geometry((x,y,depth),yaw,cx,cy,f)[0])

    x = y = 0.0

    for _ in range(9):

        lo, hi = xb

        for _ in range(26):

            mid = (lo+hi)/2

            if value(mid,y)[0] < target_h:

                lo = mid

            else:

                hi = mid

        x = (lo+hi)/2

        lo, hi = yb

        for _ in range(26):

            mid = (lo+hi)/2

            if value(x,mid)[1] < target_v:

                lo = mid

            else:

                hi = mid

        y = (lo+hi)/2

    if target_h == 0 and abs(value(0,y)[0]) < .49:

        x = 0

    if target_v == 0 and abs(value(x,0)[1]) < .49:

        y = 0

    actual_h, actual_v = value(x,y)

    if abs(actual_h-target_h) >= .49 or abs(actual_v-target_v) >= .49:

        return None

    return x,y,depth

def chosen():

    try:

        d = float(fields['Depth'].get())

        h = int(fields['Horizontal %'].get())

        v = int(fields['Vertical %'].get())

        if not (NEAR <= d <= FAR and -100 <= h <= 100 and -100 <= v <= 100):

            return None

        return d,h,v

    except ValueError:

        return None

def update_map():

    global map_job

    map_job = None

    map_canvas.delete('all')

    try:

        depth = float(fields['Depth'].get())

        yaw = 0.0

    except ValueError:

        depth = float('nan')

    if not NEAR <= depth <= FAR:

        map_canvas.create_text(110,110,text='Enter a depth from 3 to 12')

        range_text.set('Depth 3–12; X and Y from -100 to +100.')

        return

    choice = chosen()

    w,h,cx,cy,f = camera()

    im = Image.new('RGB',(MAP_SIZE,MAP_SIZE),'#f2f2f2')

    draw = ImageDraw.Draw(im)

    horizontal_values, vertical_values = [], []

    for iy in range(35):

        py = CENTER_R+(h-2*CENTER_R)*iy/34

        y = (cy-py)*depth/f

        for ix in range(47):

            px = CENTER_R+(w-2*CENTER_R)*ix/46

            x = (px-cx)*depth/f

            a,b = percentages(geometry((x,y,depth),yaw,cx,cy,f)[0])

            horizontal_values.append(a)

            vertical_values.append(b)

            mx = round((a+100)*(MAP_SIZE-1)/200)

            my = round((100-b)*(MAP_SIZE-1)/200)

            draw.ellipse((mx-2,my-2,mx+2,my+2),fill='#75b5d6')

    range_text.set(

        f'At depth {depth:g}, yaw {yaw:+.1f}°:\n'

        f'X: {math.floor(min(horizontal_values)):+d}% to '

        f'{math.ceil(max(horizontal_values)):+d}%\n'

        f'Y: {math.floor(min(vertical_values)):+d}% to '

        f'{math.ceil(max(vertical_values)):+d}%\n'

        'New boxes start at yaw 0°. Use the blue map for valid pairs.'

    )

    map_canvas.photo = ImageTk.PhotoImage(im)

    map_canvas.create_image(0,0,image=map_canvas.photo,anchor='nw')

    map_canvas.create_line(110,0,110,220,fill='#888')

    map_canvas.create_line(0,110,220,110,fill='#888')

    if choice is None:

        message.set('Enter whole X and Y percentages from -100 to +100.')

        return

    _, target_h, target_v = choice

    mx = (target_h+100)*(MAP_SIZE-1)/200

    my = (100-target_v)*(MAP_SIZE-1)/200

    valid = solve(depth,yaw,target_h,target_v) is not None

    color = '#087443' if valid else '#d02631'

    map_canvas.create_oval(mx-5,my-5,mx+5,my+5,fill=color,outline='white')

    message.set(

        'Green target: valid pair.' if valid

        else 'Red target: unavailable at this depth.'

    )

def schedule_map(event=None):

    global map_job

    if map_job is not None:

        root.after_cancel(map_job)

    map_job = root.after(120,update_map)

def update_rotation_range():

    if selected is None:

        rotation_text.set('Place a box to see its rotation range.')

        return

    box = boxes[selected]

    w,h,cx,cy,f = camera()

    bound = limit_yaw()

    cache_key = (box['pos'],w,h,bound)

    if box.get('range_key') != cache_key:

        horizontal = []

        for i in range(361):

            yaw = -bound + 2*bound*i/360

            visible,_ = geometry(box['pos'],yaw,cx,cy,f)

            horizontal.append(percentages(visible)[0])

        box['range_key'] = cache_key

        box['horizontal_range'] = (min(horizontal),max(horizontal))

    low, high = box['horizontal_range']

    low = math.ceil(low - 0.49 - 1e-9)

    high = math.floor(high + 0.49 + 1e-9)

    current = percentages(geometry(box['pos'],box['yaw'],cx,cy,f)[0])

    rotation_text.set(

        f'Box {selected+1} at depth {box["depth"]:.2f}:\n'

        f'Rotation X: {low:+d}% to '

        f'{high:+d}%\n'

        f'Now: X {current[0]:+.0f}%, Y {current[1]:+.0f}%'

    )

def paint_box(i):

    box = boxes[i]

    w,h,cx,cy,f = camera()

    visible, vertices = geometry(box['pos'],box['yaw'],cx,cy,f)

    coords = list(vertices.values())

    l = max(0,math.floor(min(x for x,y in coords))-4)

    t = max(0,math.floor(min(y for x,y in coords))-4)

    r = min(w,math.ceil(max(x for x,y in coords))+4)

    b = min(h,math.ceil(max(y for x,y in coords))+4)

    if r <= l or b <= t:

        canvas.itemconfigure(box['image'],state='hidden')

        return

    im = Image.new('RGBA',((r-l)*AA,(b-t)*AA))

    draw = ImageDraw.Draw(im)

    edge = '#8050b5' if i == selected else '#34465c'

    for p,color,_ in visible:

        q = [((x-l)*AA,(y-t)*AA) for x,y in p]

        draw.polygon(q,fill=color)

        draw.line(q+[q[0]],fill=edge,width=AA*2,joint='curve')

    box['photo'] = ImageTk.PhotoImage(

        im.resize((r-l,b-t),Image.Resampling.LANCZOS)

    )

    canvas.itemconfigure(box['image'],image=box['photo'],state='normal')

    canvas.coords(box['image'],l,t)

    px,py = project(box['pos'],cx,cy,f)

    rr = CENTER_R if i == selected else 2

    canvas.coords(box['center'],px-rr,py-rr,px+rr,py+rr)

    hh,vv = percentages(visible)

    canvas.itemconfigure(box['label'],text=f'({hh:+.0f}, {vv:+.0f})')

    canvas.coords(box['label'],px,py+12)

def paint_dot(x,y):

    left,top = math.floor(x-DOT_R-2),math.floor(y-DOT_R-2)

    side = DOT_R*2+5

    im = Image.new('RGBA',(side*AA,side*AA))

    draw = ImageDraw.Draw(im)

    draw.ellipse(

        ((x-DOT_R-left)*AA,(y-DOT_R-top)*AA,

         (x+DOT_R-left)*AA,(y+DOT_R-top)*AA),

        outline='#008e73',width=2*AA

    )

    root.dot_photo = ImageTk.PhotoImage(

        im.resize((side,side),Image.Resampling.LANCZOS)

    )

    canvas.itemconfigure('dot',image=root.dot_photo,state='normal')

    canvas.coords('dot',left,top)

def guide():

    canvas.delete('guide')

    canvas.itemconfigure('dot',state='hidden')

    if selected is None:

        return

    box = boxes[selected]

    _,_,cx,cy,f = camera()

    a = math.radians(box['yaw'])

    c,s = math.cos(a),math.sin(a)

    if guide_on:

        bx,by,bz = box['pos']

        e = SIZE*2

        x1,y1 = project((bx-e*s,by,bz-e*c),cx,cy,f)

        x2,y2 = project((bx+e*s,by,bz+e*c),cx,cy,f)

        canvas.create_line(

            x1,y1,x2,y2,fill='#008e73',width=2,

            dash=(5,4),tags='guide'

        )

        paint_dot(cx+f*math.tan(a),cy)

    canvas.create_text(

        12,12,anchor='nw',fill='#34465c',

        font=('Arial',12,'bold'),

        text=f"Box {selected+1}  Yaw: {box['yaw']:+.0f}°  "

             f"Depth: {box['depth']:.2f}  [G] guide",

        tags='guide'

    )

    for tag in ('guide','center','label','dot'):

        canvas.tag_raise(tag)

def redraw(event=None):

    w,h,cx,cy,f = camera()

    canvas.coords('horizon',0,cy,w,cy)

    canvas.coords('origin',cx-4,cy-4,cx+4,cy+4)

    bound = limit_yaw()

    yaw_control.configure(from_=-bound,to=bound)

    for i,box in enumerate(boxes):

        box['yaw'] = max(-bound,min(bound,box['yaw']))

        x,y,z = box['pos']

        px,py = project((x,y,z),cx,cy,f)

        px = max(CENTER_R,min(w-CENTER_R,px))

        py = max(CENTER_R,min(h-CENTER_R,py))

        box['pos'] = ((px-cx)*z/f,(cy-py)*z/f,z)

        paint_box(i)

    guide()

    update_rotation_range()

    schedule_map()

def inside(px,py,poly):

    result = False

    for i,(x1,y1) in enumerate(poly):

        x2,y2 = poly[(i+1)%len(poly)]

        if (y1>py)!=(y2>py) and px < x1+(py-y1)*(x2-x1)/(y2-y1):

            result = not result

    return result

def select_box(event):

    global selected

    canvas.focus_set()

    _,_,cx,cy,f = camera()

    for i in range(len(boxes)-1,-1,-1):

        visible,_ = geometry(

            boxes[i]['pos'],boxes[i]['yaw'],cx,cy,f

        )

        if any(inside(event.x,event.y,p) for p,_,_ in visible):

            old = selected

            selected = i

            if old is not None and old != i:

                paint_box(old)

            paint_box(i)

            set_slider(boxes[i]['yaw'])

            guide()

            update_rotation_range()

            refresh_controls()

            return

def refresh_controls():

    has_box = selected is not None

    yaw_control.configure(state='normal' if has_box else 'disabled')

def create_box(event=None):

    global selected

    choice = chosen()

    if choice is None:

        message.set('Depth 3–12; whole percentages from -100 to +100.')

        return

    depth,h,v = choice

    yaw = 0.0

    pos = solve(depth,yaw,h,v)

    if pos is None:

        message.set(

            'That percentage pair has no valid placement at this depth.'

        )

        return

    old = selected

    box = dict(pos=pos,yaw=yaw,depth=depth,photo=None)

    box['image'] = canvas.create_image(0,0,anchor='nw',tags='box')

    box['center'] = canvas.create_oval(

        0,0,0,0,fill='#8037bf',outline='',tags='center'

    )

    box['label'] = canvas.create_text(

        0,0,fill='#34224a',font=('Arial',10,'bold'),tags='label'

    )

    boxes.append(box)

    selected = len(boxes)-1

    refresh_controls()

    set_slider(0)

    if old is not None:

        paint_box(old)

    paint_box(selected)

    guide()

    update_rotation_range()

    message.set(

        f'Created Box {selected+1}: ({h:+d}, {v:+d}), '

        f'depth {depth:g}, yaw {yaw:+.1f}°.'

    )

def key_down(event):

    key = event.keysym

    if key not in ('Left','Right','Up','Down','Shift_L','Shift_R'):

        return

    job = releases.pop(key,None)

    if job is not None:

        root.after_cancel(job)

    held.add(key)

def key_up(event):

    key = event.keysym

    if key not in ('Left','Right','Up','Down','Shift_L','Shift_R'):

        return

    job = releases.pop(key,None)

    if job is not None:

        root.after_cancel(job)

    def release():

        held.discard(key)

        releases.pop(key,None)

    releases[key] = root.after(80,release)

def focus_out(event=None):

    held.clear()

    for job in releases.values():

        root.after_cancel(job)

    releases.clear()

def frame():

    global last_time

    now = time.perf_counter()

    dt = min(now-last_time,.05)

    last_time = now

    turn = int('Left' in held)-int('Right' in held)

    if selected is not None and turn:

        box = boxes[selected]

        fine = 'Shift_L' in held or 'Shift_R' in held

        speed = FINE_TURN if fine else TURN_SPEED

        yaw = max(

            -limit_yaw(),

            min(limit_yaw(),box['yaw']+turn*speed*dt)

        )

        if yaw != box['yaw']:

            box['yaw'] = yaw

            set_slider(yaw)

            paint_box(selected)

            guide()

            update_rotation_range()

    root.after(8,frame)

def clear(event=None):

    global selected

    boxes.clear()

    selected = None

    refresh_controls()

    set_slider(0)

    for tag in ('box','center','label','guide'):

        canvas.delete(tag)

    canvas.itemconfigure('dot',state='hidden')

    update_rotation_range()

def reset(event=None):

    if selected is not None:

        boxes[selected]['yaw'] = 0

        set_slider(0)

        paint_box(selected)

        guide()

        update_rotation_range()

def toggle(event=None):

    global guide_on

    guide_on = not guide_on

    guide()

def set_slider(yaw):

    global syncing_yaw

    syncing_yaw = True

    angle_var.set(yaw)

    syncing_yaw = False

def slider_turn(value):

    if syncing_yaw or selected is None:

        return

    box = boxes[selected]

    yaw = float(value)

    if yaw != box['yaw']:

        box['yaw'] = yaw

        paint_box(selected)

        guide()

        update_rotation_range()

from concurrent.futures import ThreadPoolExecutor

from pathlib import Path

import wave

import winsound

VOICE_MODEL = Path(__file__).resolve().parent / 'en_US-lessac-medium.onnx'

VOICE_CONFIG = Path(str(VOICE_MODEL) + '.json')

WELCOME_SPOKEN = (

    'Welcome to Perspective Boxes. Use Instructions or commands to know your next step.'

)

INSTRUCTIONS_OPENED_SPOKEN = 'Instructions opened.'

CREATE_PROMPT_SPOKEN = (

    'Ready to create. Start by selecting the depth, from three to twelve.'

)

VOICE_CACHE = Path.home() / 'AppData' / 'Local' / 'PerspectiveBoxes' / 'voice_cache'

VOICE_CACHE.mkdir(parents=True, exist_ok=True)

VOICE_EXECUTOR = ThreadPoolExecutor(max_workers=1)

VOICE_FUTURES = {}

VOICE_LOADED = {'model': None}

def prepare_voice(key, value):

    if key in VOICE_FUTURES:

        return VOICE_FUTURES[key]

    def render():

        from piper import PiperVoice, SynthesisConfig

        output = VOICE_CACHE / f'{key}.wav'

        if output.is_file():

            return str(output)

        if VOICE_LOADED['model'] is None:

            VOICE_LOADED['model'] = PiperVoice.load(str(VOICE_MODEL))

        with wave.open(str(output), 'wb') as wav_file:

            VOICE_LOADED['model'].synthesize_wav(

                value, wav_file,

                syn_config=SynthesisConfig(length_scale=1.05)

            )

        return str(output)

    VOICE_FUTURES[key] = VOICE_EXECUTOR.submit(render)

    return VOICE_FUTURES[key]

def show_instructions():

    existing = getattr(root, 'instructions_window', None)

    if existing is not None and existing.winfo_exists():

        existing.lift()

        existing.focus_force()

        return

    window = tk.Toplevel(root)

    root.instructions_window = window

    window.title('Instructions — Perspective Boxes')

    window.geometry('650x560')

    window.minsize(460, 380)

    sections = [

        ('TO CREATE A BOX',

         'First, choose a depth from 3 to 12. 3 is closest, 12 is farthest, '

         'and 6 is the default.\n\n'

         'Second, the app shows the possible horizontal and vertical percentage '

         'ranges for that depth. Choose a value from each range.\n\n'

         'Third, press Create box or Enter. The box is placed at your chosen '

         'position with zero degree yaw, meaning its vanishing point is at the '

         'center of the canvas.'),

        ('WHAT THE PERCENTAGES MEAN',

         'The percentages are not screen coordinates. They describe how much '

         'of the box’s side, top, or bottom face is visible at its position '

         'relative to the center vanishing point.\n\n'

         'Positive horizontal: left face visible.\n'

         'Negative horizontal: right face visible.\n'

         'Positive vertical: bottom face visible.\n'

         'Negative vertical: top face visible.\n\n'

         'For example, negative 20, negative 30 means approximately 20 percent '

         'right-face visibility and 30 percent top-face visibility.'),

        ('TO SELECT AND ROTATE',

         'Click a box to select it. Its outline turns purple. Hold Left or '

         'Right to rotate it. The box stays at the same center position and '

         'depth.\n\n'

         'The app shows the horizontal percentage range through which the '

         'selected box can rotate. Rotation moves its vanishing point: Left '

         'moves the vanishing point right and makes more of the box’s right '

         'face visible; Right moves it left and makes more of the left face '

         'visible. The vertical percentage stays the same.\n\n'

         'You can also say “rotation.” When asked, say the box number, then '

         'say a rotation X value from the range announced by the app. A '

         'negative value moves the default center vanishing point to the '

         'right; a positive value moves it to the left.'),

    ]

    tk.Label(window, text='Choose an option (or press 1–3):',

             font=('Arial', 13, 'bold')).pack(pady=(12, 6))

    buttons = tk.Frame(window)

    buttons.pack(fill='x', padx=12)

    content = tk.Frame(window, padx=12, pady=12)

    content.pack(fill='both', expand=True)

    scrollbar = tk.Scrollbar(content)

    scrollbar.pack(side='right', fill='y')

    help_text = tk.Text(content, wrap='word', yscrollcommand=scrollbar.set,

                        font=('Arial', 12), padx=12, pady=12)

    help_text.pack(side='left', fill='both', expand=True)

    scrollbar.configure(command=help_text.yview)

    def show_text(value):

        help_text.configure(state='normal')

        help_text.delete('1.0', 'end')

        help_text.insert('1.0', value)

        help_text.configure(state='disabled')

    def select_topic(index):

        title, value = sections[index]

        show_text(title + '\n\n' + value)

    for i, (title, _) in enumerate(sections):

        tk.Button(buttons, text=f'{i + 1}. {title}',

                  command=lambda index=i: select_topic(index)).pack(

                      fill='x', pady=2)

        window.bind(str(i + 1), lambda event, index=i: select_topic(index))

    show_text('Choose an option:\n\n' + '\n'.join(

        f'{i}. {title}' for i, (title, _) in enumerate(sections, 1)

    ))

    window.protocol('WM_DELETE_WINDOW', window.destroy)

    window.bind('<Escape>', lambda event: window.destroy())

    tk.Button(window, text='Close', command=window.destroy).pack(pady=(0, 12))

for entry in fields.values():

    entry.bind('<KeyRelease>',schedule_map)

yaw_control.configure(command=slider_turn)

tk.Button(

    bar,text='Create box',command=create_box

).pack(side='left',padx=8)

tk.Button(

    bar,text='Instructions',command=show_instructions

).pack(side='left',padx=4)

canvas.create_line(0,0,0,0,fill='#aaa',tags='horizon')

canvas.create_oval(0,0,0,0,fill='red',outline='',tags='origin')

canvas.create_image(0,0,anchor='nw',state='hidden',tags='dot')

canvas.bind('<Button-1>',select_box)

canvas.bind('<Configure>',redraw)

root.bind(

    '<Return>',

    create_box

)

root.bind('<KeyPress>',key_down)

root.bind('<KeyRelease>',key_up)

root.bind('<FocusOut>',focus_out)

root.bind('<r>',reset)

root.bind('<c>',clear)

root.bind('<g>',toggle)

root.bind('<Escape>',lambda event:root.destroy())

def set_voice_status(text):

    voice_events.put(('status', text))

def process_voice_events():

    while True:

        try:

            kind, value = voice_events.get_nowait()

        except queue.Empty:

            break

        if kind == 'status':

            voice_status.set(value)

        elif kind == 'instructions':

            open_instructions_by_voice()

        elif kind == 'voice_ready':

            welcome_user()

        elif kind == 'create_prompt':

            play_voice_when_ready('create_prompt', CREATE_PROMPT_SPOKEN)

        elif kind == 'create_box':

            create_box_by_voice(*value)

        elif kind == 'depth_selected':

            ask_for_horizontal(value)

        elif kind == 'horizontal_selected':

            confirm_horizontal_and_ask_vertical(*value)

        elif kind == 'horizontal_retry':

            ask_for_horizontal(value[0])

        elif kind == 'vertical_retry':

            ask_for_vertical(*value)

        elif kind == 'rotation_begin':

            begin_rotation_voice_flow()

        elif kind == 'rotation_box_retry':

            ask_for_rotation_box()

        elif kind == 'rotation_box_selected':

            select_rotation_box(value)

        elif kind == 'rotation_value_retry':

            ask_for_rotation_value()

        elif kind == 'rotation_value_selected':

            apply_rotation_by_voice(*value)

    root.after(30, process_voice_events)

def play_voice_when_ready(key, text):

    future = prepare_voice(key, text)

    def check():

        global voice_echo_ignore_until

        try:

            if not future.done():

                root.after(40, check)

                return

            audio_path = future.result()

            with wave.open(audio_path, 'rb') as wav_file:

                duration = wav_file.getnframes() / wav_file.getframerate()

            voice_echo_ignore_until = time.monotonic() + duration + 0.6

            winsound.PlaySound(

                audio_path, winsound.SND_FILENAME | winsound.SND_ASYNC

            )

        except Exception as exc:

            set_voice_status(f'Voice playback unavailable: {exc}')

    root.after(0, check)

def welcome_user():

    if VOICE_MODEL.is_file() and VOICE_CONFIG.is_file():

        play_voice_when_ready('welcome', WELCOME_SPOKEN)

    else:

        set_voice_status('Voice model files were not found.')

def precache_instruction_confirmation():

    if VOICE_MODEL.is_file() and VOICE_CONFIG.is_file():

        prepare_voice('welcome', WELCOME_SPOKEN)

        prepare_voice('instructions_opened', INSTRUCTIONS_OPENED_SPOKEN)

        prepare_voice('create_prompt', CREATE_PROMPT_SPOKEN)

def open_instructions_by_voice():

    show_instructions()

    if VOICE_MODEL.is_file() and VOICE_CONFIG.is_file():

        play_voice_when_ready(

            'instructions_opened', INSTRUCTIONS_OPENED_SPOKEN

        )

def number_word(number):

    if number < 0:

        return f'negative {number_word(abs(number))}'

    words = {

        0: 'zero', 1: 'one', 2: 'two', 3: 'three', 4: 'four',

        5: 'five', 6: 'six', 7: 'seven', 8: 'eight', 9: 'nine',

        10: 'ten', 11: 'eleven', 12: 'twelve', 13: 'thirteen',

        14: 'fourteen', 15: 'fifteen', 16: 'sixteen',

        17: 'seventeen', 18: 'eighteen', 19: 'nineteen',

        20: 'twenty', 30: 'thirty', 40: 'forty', 50: 'fifty',

        60: 'sixty', 70: 'seventy', 80: 'eighty', 90: 'ninety',

    }

    if number in words:

        return words[number]

    if 21 <= number <= 99:

        tens = number // 10 * 10

        return f'{words[tens]} {words[number % 10]}'

    return str(number)

def parse_spoken_integer(command):

    command = command.strip()

    sign = 1

    if command.startswith('-'):

        sign = -1

        command = command[1:].strip()

    else:

        command = command.replace('-', ' ')

    for prefix in ('negative ', 'minus '):

        if command.startswith(prefix):

            sign = -1

            command = command[len(prefix):].strip()

            break

    else:

        if command.startswith('plus '):

            command = command[5:].strip()

    if command.isdigit():

        return sign * int(command)

    small_numbers = {

        'zero': 0, 'oh': 0, 'one': 1, 'two': 2, 'three': 3,

        'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8,

        'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,

        'thirteen': 13, 'fourteen': 14, 'fifteen': 15,

        'sixteen': 16, 'seventeen': 17, 'eighteen': 18,

        'nineteen': 19,

    }

    tens = {

        'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50,

        'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90,

    }

    words = command.split()

    if len(words) == 1:

        value = small_numbers.get(words[0], tens.get(words[0]))

        return sign * value if value is not None else None

    if len(words) == 2 and words[0] in tens and words[1] in small_numbers:

        ones = small_numbers[words[1]]

        if 1 <= ones <= 9:

            return sign * (tens[words[0]] + ones)

    return None

def horizontal_range_for_depth(depth):

    w, h, cx, cy, f = camera()

    left_x = (CENTER_R - cx) * depth / f

    right_x = (w - CENTER_R - cx) * depth / f

    left_value = percentages(

        geometry((left_x, 0, depth), 0, cx, cy, f)[0]

    )[0]

    right_value = percentages(

        geometry((right_x, 0, depth), 0, cx, cy, f)[0]

    )[0]

    # solve() accepts a target within 0.49 percentage points of the edge.

    low = math.ceil(min(left_value, right_value) - 0.49 - 1e-9)

    high = math.floor(max(left_value, right_value) + 0.49 + 1e-9)

    return low, high

def ask_for_horizontal(depth):

    low, high = horizontal_range_for_depth(depth)

    voice_flow.update(

        phase='horizontal', depth=depth,

        horizontal_min=low, horizontal_max=high,

    )

    box_number = len(boxes) + 1

    spoken = (

        f'Box {number_word(box_number)} will be placed at depth '

        f'{number_word(depth)}. Where do you want its horizontal value? '

        f'Choose between {number_word(low)} and {number_word(high)}.'

    )

    set_voice_status(

        f'Choose horizontal from {low} to {high} at depth {depth}.'

    )

    speak_dynamic(spoken)

def vertical_range_for_selection(depth, horizontal):

    valid_values = [

        vertical for vertical in range(-100, 101)

        if solve(depth, 0.0, horizontal, vertical) is not None

    ]

    if not valid_values:

        return None

    return min(valid_values), max(valid_values)

def horizontal_description(horizontal):

    if horizontal == 0:

        return 'with no side face visible.'

    if horizontal < 0:

        return (

            f'with {number_word(abs(horizontal))} percent of the '

            'right face visible.'

        )

    return (

        f'with {number_word(horizontal)} percent of the '

        'left face visible.'

    )

def vertical_description(vertical):

    if vertical == 0:

        return 'with no top or bottom visible.'

    if vertical < 0:

        return (

            f'with {number_word(abs(vertical))} percent of the '

            'top visible.'

        )

    return (

        f'with {number_word(vertical)} percent of the '

        'bottom visible.'

    )

def confirm_horizontal_and_ask_vertical(depth, horizontal):

    limits = vertical_range_for_selection(depth, horizontal)

    if limits is None:

        set_voice_status('No vertical placement is available for that horizontal value.')

        voice_flow['phase'] = 'horizontal'

        ask_for_horizontal(depth)

        return

    low, high = limits

    voice_flow.update(

        phase='vertical', depth=depth, horizontal=horizontal,

        vertical_min=low, vertical_max=high,

    )

    box_number = len(boxes) + 1

    spoken = (

        f'Box {number_word(box_number)} placed at horizontal '

        f'{number_word(horizontal)}, {horizontal_description(horizontal)} '

        f'Next, where do you want your vertical to be? Choose between '

        f'{number_word(low)} and {number_word(high)}.'

    )

    set_voice_status(

        f'Horizontal {horizontal} selected. Choose vertical from {low} to {high}.'

    )

    speak_dynamic(spoken)

def ask_for_vertical(depth, horizontal, low=None, high=None):

    if low is None or high is None:

        limits = vertical_range_for_selection(depth, horizontal)

        if limits is None:

            return

        low, high = limits

    voice_flow.update(

        phase='vertical', depth=depth, horizontal=horizontal,

        vertical_min=low, vertical_max=high,

    )

    spoken = (

        f'Please choose a vertical value between '

        f'{number_word(low)} and {number_word(high)}.'

    )

    set_voice_status(f'Choose vertical from {low} to {high}.')

    speak_dynamic(spoken)

def create_box_by_voice(depth, horizontal, vertical):

    fields['Depth'].delete(0, 'end')

    fields['Depth'].insert(0, str(depth))

    fields['Horizontal %'].delete(0, 'end')

    fields['Horizontal %'].insert(0, str(horizontal))

    fields['Vertical %'].delete(0, 'end')

    fields['Vertical %'].insert(0, str(vertical))

    schedule_map()

    previous_count = len(boxes)

    create_box()

    if len(boxes) == previous_count:

        set_voice_status('Could not create a box at that position.')

        return

    box_number = len(boxes)

    vertical_spoken = (

        f'Box {number_word(box_number)} placed at vertical '

        f'{number_word(vertical)}, {vertical_description(vertical)} '

    )

    final_spoken = (

        f'Box {number_word(box_number)} placed at horizontal '

        f'{number_word(horizontal)} and vertical {number_word(vertical)} successfully.'

    )

    set_voice_status(

        f'Box {box_number} placed successfully at horizontal {horizontal}, vertical {vertical}.'

    )

    speak_dynamic(vertical_spoken + final_spoken)

def speak_dynamic(spoken):

    key = 'dynamic_' + hashlib.sha1(

        spoken.encode('utf-8')

    ).hexdigest()[:16]

    play_voice_when_ready(key, spoken)



def begin_rotation_voice_flow():

    if not boxes:

        voice_flow['phase'] = None

        set_voice_status('There are no boxes to rotate yet.')

        speak_dynamic('There are no boxes to rotate yet. Say create to place one.')

        return

    ask_for_rotation_box()



def ask_for_rotation_box():

    voice_flow['phase'] = 'rotation_box'

    count = len(boxes)

    spoken = (

        'Understood. Which box do you want to rotate? '

        f'Say a number from one to {number_word(count)}.'

    )

    set_voice_status(f'Say the box number from 1 to {count}.')

    speak_dynamic(spoken)



def select_box_by_index(index):

    global selected

    if not 0 <= index < len(boxes):

        return False

    old = selected

    selected = index

    refresh_controls()

    set_slider(boxes[index]['yaw'])

    if old is not None and old != index:

        paint_box(old)

    paint_box(index)

    guide()

    update_rotation_range()

    return True



def select_rotation_box(index):

    if not select_box_by_index(index):

        voice_flow['phase'] = 'rotation_box'

        ask_for_rotation_box()

        return

    box = boxes[index]

    w, h, cx, cy, f = camera()

    current_h, current_v = percentages(

        geometry(box['pos'], box['yaw'], cx, cy, f)[0]

    )

    low_value, high_value = box['horizontal_range']

    low = math.ceil(low_value - 0.49 - 1e-9)

    high = math.floor(high_value + 0.49 + 1e-9)

    voice_flow.update(

        phase='rotation_value', rotation_box=index,

        rotation_min=low, rotation_max=high,

    )

    box_number = index + 1

    spoken = (

        f'Box number {number_word(box_number)} has been selected. '

        f'It is currently at horizontal {number_word(round(current_h))}, '

        f'vertical {number_word(round(current_v))}, at depth '

        f'{number_word(box["depth"])}. At this location, its rotation X '

        f'range is {number_word(low)} to {number_word(high)}. '

        'Select your rotation X number.'

    )

    set_voice_status(

        f'Box {box_number} selected. Rotation X range: {low} to {high}.'

    )

    speak_dynamic(spoken)



def ask_for_rotation_value():

    low = voice_flow['rotation_min']

    high = voice_flow['rotation_max']

    spoken = (

        f'Please choose a rotation X value from '

        f'{number_word(low)} to {number_word(high)}.'

    )

    set_voice_status(f'Choose rotation X from {low} to {high}.')

    speak_dynamic(spoken)



def find_yaw_for_rotation_x(box, target):

    bound = limit_yaw()

    w, h, cx, cy, f = camera()



    def horizontal_at(yaw):

        visible = geometry(box['pos'], yaw, cx, cy, f)[0]

        return percentages(visible)[0]



    left_yaw, right_yaw = -bound, bound

    left_value, right_value = horizontal_at(left_yaw), horizontal_at(right_yaw)

    if not min(left_value, right_value) - 0.49 <= target <= max(

        left_value, right_value

    ) + 0.49:

        return None



    increasing = right_value >= left_value

    for _ in range(45):

        middle_yaw = (left_yaw + right_yaw) / 2

        middle_value = horizontal_at(middle_yaw)

        if (middle_value < target) == increasing:

            left_yaw = middle_yaw

        else:

            right_yaw = middle_yaw



    yaw = (left_yaw + right_yaw) / 2

    actual = horizontal_at(yaw)

    if abs(actual - target) > 0.49:

        return None

    return yaw, actual



def apply_rotation_by_voice(index, target):

    if not 0 <= index < len(boxes):

        ask_for_rotation_box()

        return

    box = boxes[index]

    result = find_yaw_for_rotation_x(box, target)

    if result is None:

        voice_flow['phase'] = 'rotation_value'

        ask_for_rotation_value()

        return



    yaw, actual = result

    select_box_by_index(index)

    box['yaw'] = yaw

    box.pop('range_key', None)

    set_slider(yaw)

    paint_box(index)

    guide()

    update_rotation_range()

    voice_flow['phase'] = None



    if target < 0:

        direction = 'The default center vanishing point moved to the right.'

    elif target > 0:

        direction = 'The default center vanishing point moved to the left.'

    else:

        direction = 'The vanishing point remains at the default center.'

    spoken = (

        f'Rotation X is {number_word(target)}. {direction}'

    )

    set_voice_status(

        f'Box {index + 1} rotated to X {actual:+.0f}. {direction}'

    )

    speak_dynamic(spoken)

def voice_command_loop():

    welcome_ready = False

    if sr is None:

        set_voice_status(

            'Voice commands need faster-whisper, SpeechRecognition, and PyAudio.'

        )

        voice_events.put(('voice_ready', None))

        return

    try:

        import numpy as np

        from faster_whisper import WhisperModel

    except ImportError as exc:

        set_voice_status(

            'Voice commands need faster-whisper and NumPy. '

            f'Install them with: python -m pip install faster-whisper. ({exc})'

        )

        voice_events.put(('voice_ready', None))

        return

    recognizer = sr.Recognizer()

    recognizer.dynamic_energy_threshold = True

    recognizer.dynamic_energy_adjustment_ratio = 1.0

    recognizer.pause_threshold = 0.6

    recognizer.non_speaking_duration = 0.3

    recognizer.phrase_threshold = 0.25

    last_command_time = 0.0

    try:

        # Calibrate the microphone before starting the continuous listener.

        with sr.Microphone() as source:

            recognizer.adjust_for_ambient_noise(source, duration=0.8)

        voice_events.put(('voice_ready', None))

        welcome_ready = True

    except Exception as exc:

        set_voice_status(f'Microphone unavailable: {exc}')

        if not welcome_ready:

            voice_events.put(('voice_ready', None))

        return

    set_voice_status('Loading offline speech model; first run may download it...')

    try:

        # CPU int8 keeps the always-on listener practical on ordinary laptops.

        # faster-whisper applies its bundled Silero VAD to each captured phrase.

        model = WhisperModel('base.en', device='cpu', compute_type='int8')

    except Exception as exc:

        set_voice_status(f'Could not load the offline speech model: {exc}')

        return

    audio_queue = queue.Queue(maxsize=2)

    def on_audio(recognizer_instance, audio):

        # Keep only recent speech if transcription briefly falls behind.

        if time.monotonic() < voice_echo_ignore_until:

            return

        try:

            audio_queue.put_nowait(audio)

        except queue.Full:

            try:

                audio_queue.get_nowait()

            except queue.Empty:

                pass

            try:

                audio_queue.put_nowait(audio)

            except queue.Full:

                pass

    try:

        stop_listening = recognizer.listen_in_background(

            sr.Microphone(), on_audio, phrase_time_limit=4

        )

        set_voice_status("Voice control listening for 'instructions', 'create', or 'rotation'.")

        while True:

            audio = audio_queue.get()

            try:

                # faster-whisper expects mono float audio sampled at 16 kHz.

                pcm = audio.get_raw_data(convert_rate=16000, convert_width=2)

                samples = (

                    np.frombuffer(pcm, dtype=np.int16).astype(np.float32)

                    / 32768.0

                )

                segments, _ = model.transcribe(

                    samples,

                    language='en',

                    beam_size=1,

                    best_of=1,

                    temperature=0.0,

                    condition_on_previous_text=False,

                    without_timestamps=True,

                    vad_filter=True,

                    vad_parameters={

                        'min_silence_duration_ms': 300,

                        'speech_pad_ms': 250,

                    },

                )

                transcript = ' '.join(

                    segment.text.strip() for segment in segments

                ).strip()

                command = re.sub(

                    r'[^a-z0-9-]+', ' ', transcript.lower()

                ).strip()

            except Exception as exc:

                set_voice_status(f'Offline speech recognition error: {exc}')

                continue

            now = time.monotonic()

            if command == 'instructions' and now - last_command_time > 2:

                voice_flow['phase'] = None

                last_command_time = now

                voice_events.put(('instructions', None))

            elif command == 'rotation' and now - last_command_time > 2:

                voice_flow['phase'] = 'rotation_box_pending'

                last_command_time = now

                voice_events.put(('rotation_begin', None))

            elif command == 'create' and now - last_command_time > 2:

                voice_flow.update(phase='depth', depth=None)

                last_command_time = now

                voice_events.put(('create_prompt', None))

            elif voice_flow['phase'] == 'depth':

                depth = parse_spoken_integer(command)

                if depth is not None and 3 <= depth <= 12:

                    voice_flow.update(phase='horizontal_pending', depth=depth)

                    last_command_time = now

                    voice_events.put(('depth_selected', depth))

            elif voice_flow['phase'] == 'horizontal':

                horizontal = parse_spoken_integer(command)

                low = voice_flow['horizontal_min']

                high = voice_flow['horizontal_max']

                depth = voice_flow['depth']

                if horizontal is None:

                    continue

                if low <= horizontal <= high:

                    voice_flow.update(

                        phase='vertical_pending', horizontal=horizontal

                    )

                    last_command_time = now

                    voice_events.put((

                        'horizontal_selected', (depth, horizontal)

                    ))

                else:

                    voice_events.put((

                        'horizontal_retry', (depth, low, high)

                    ))

            elif voice_flow['phase'] == 'vertical':

                vertical = parse_spoken_integer(command)

                low = voice_flow['vertical_min']

                high = voice_flow['vertical_max']

                depth = voice_flow['depth']

                horizontal = voice_flow['horizontal']

                if vertical is None:

                    continue

                if low <= vertical <= high and solve(

                    depth, 0.0, horizontal, vertical

                ) is not None:

                    voice_flow['phase'] = None

                    last_command_time = now

                    voice_events.put((

                        'create_box', (depth, horizontal, vertical)

                    ))

                else:

                    voice_events.put((

                        'vertical_retry', (depth, horizontal, low, high)

                    ))

            elif voice_flow['phase'] == 'rotation_box':

                box_number = parse_spoken_integer(command)

                if box_number is None:

                    continue

                if 1 <= box_number <= len(boxes):

                    index = box_number - 1

                    voice_flow.update(

                        phase='rotation_value_pending', rotation_box=index

                    )

                    last_command_time = now

                    voice_events.put(('rotation_box_selected', index))

                else:

                    voice_events.put(('rotation_box_retry', None))

            elif voice_flow['phase'] == 'rotation_value':

                target = parse_spoken_integer(command)

                if target is None:

                    continue

                low = voice_flow['rotation_min']

                high = voice_flow['rotation_max']

                if low <= target <= high:

                    index = voice_flow['rotation_box']

                    voice_flow['phase'] = 'rotation_applying'

                    last_command_time = now

                    voice_events.put((

                        'rotation_value_selected', (index, target)

                    ))

                else:

                    voice_events.put((

                        'rotation_value_retry', (low, high)

                    ))

    except Exception as exc:

        set_voice_status(f'Microphone unavailable: {exc}')

def start_voice_listener():

    threading.Thread(target=voice_command_loop, daemon=True).start()

root.after(8,frame)

root.after(200,update_map)

root.after(0, precache_instruction_confirmation)

root.after(0, start_voice_listener)

root.after(30, process_voice_events)

root.mainloop()
