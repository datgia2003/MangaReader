import copy
import json
import os
import sys
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageDraw
from detector import Panel, detect_panels, export_page, make_crop, natural_key, read_image, reading_order, split_polygon, save_session, load_session

BG, CARD, FG, ACCENT = '#11151d', '#1b2230', '#edf2fa', '#70e1cc'


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Manga Panel Cutter — cắt panel để đưa vào Flow')
        self.geometry('1400x900'); self.minsize(1050, 700); self.configure(bg=BG)
        self.entries, self.index, self.selected = [], -1, []
        self.mode, self.pending, self.dragging = 'select', [], None
        self.history, self.jobs, self.busy = [], queue.Queue(), False
        self.scale, self.offset, self.zoom = 1, (0, 0), 1
        self.sensitivity = tk.DoubleVar(value=1.0)
        style = ttk.Style(self); style.theme_use('clam')
        style.configure('.', background=CARD, foreground=FG, font=('Segoe UI', 10))
        style.configure('TButton', padding=(10, 7), background='#283548')
        style.map('TButton', background=[('active', '#3a516e')])
        style.configure('Accent.TButton', background='#246a62')
        top = ttk.Frame(self, padding=10); top.pack(fill='x')
        for text, fn in [('Chọn ảnh…', self.choose), ('Chọn thư mục…', self.folder), ('Mở phiên…', self.open_session), ('Lưu phiên…', self.save), ('Hướng dẫn', self.help)]:
            ttk.Button(top, text=text, command=fn).pack(side='left', padx=3)
        ttk.Button(top, text='Xuất tất cả…', style='Accent.TButton', command=self.export_all).pack(side='right', padx=3)
        ttk.Button(top, text='Xuất trang này…', command=self.export_current).pack(side='right', padx=3)
        body = ttk.Frame(self); body.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        left = ttk.Frame(body, width=220, padding=8); left.pack(side='left', fill='y'); left.pack_propagate(False)
        ttk.Label(left, text='TRANG MANGA').pack(anchor='w', pady=5)
        self.pages = tk.Listbox(left, bg=BG, fg=FG, selectbackground='#286d64', borderwidth=0, highlightthickness=0, font=('Segoe UI', 10))
        self.pages.pack(fill='both', expand=True); self.pages.bind('<<ListboxSelect>>', self.page_selected)
        ttk.Label(left, text='Độ nhạy tách khung').pack(anchor='w', pady=(12, 0))
        ttk.Scale(left, from_=.75, to=1.6, variable=self.sensitivity).pack(fill='x')
        ttk.Button(left, text='Tự cắt trang này', command=self.auto_current).pack(fill='x', pady=4)
        ttk.Button(left, text='Tự cắt tất cả', command=self.auto_all).pack(fill='x', pady=4)
        middle = ttk.Frame(body); middle.pack(side='left', fill='both', expand=True, padx=10)
        toolbar = ttk.Frame(middle); toolbar.pack(fill='x', pady=(0, 6))
        for text, mode in [('Chọn / kéo góc', 'select'), ('Vẽ panel', 'add'), ('Chia panel', 'split')]:
            ttk.Button(toolbar, text=text, command=lambda m=mode: self.set_mode(m)).pack(side='left', padx=2)
        ttk.Button(toolbar, text='Gộp', command=self.merge).pack(side='left', padx=2)
        ttk.Button(toolbar, text='Xóa', command=self.delete).pack(side='left', padx=2)
        ttk.Button(toolbar, text='Hoàn tác', command=self.undo).pack(side='left', padx=2)
        ttk.Button(toolbar, text='Vừa màn hình', command=self.fit).pack(side='right')
        self.canvas = tk.Canvas(middle, bg='#080c12', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda e: self.draw())
        self.canvas.bind('<Button-1>', self.click); self.canvas.bind('<B1-Motion>', self.motion); self.canvas.bind('<ButtonRelease-1>', self.release)
        self.canvas.bind('<Double-Button-1>', self.finish_polygon); self.canvas.bind('<MouseWheel>', self.wheel)
        self.canvas.bind('<Button-3>', lambda e: self.cancel())
        self.bind('<Escape>', lambda e: self.cancel()); self.bind('<Return>', self.finish_polygon)
        self.bind('<Control-z>', lambda e: self.undo()); self.bind('<Delete>', lambda e: self.delete())
        right = ttk.Frame(body, width=250, padding=8); right.pack(side='right', fill='y'); right.pack_propagate(False)
        ttk.Label(right, text='PANEL / THỨ TỰ ĐỌC').pack(anchor='w', pady=5)
        self.panel_list = tk.Listbox(right, bg=BG, fg=FG, selectbackground='#286d64', selectmode='extended', exportselection=False, borderwidth=0, highlightthickness=0, height=13)
        self.panel_list.pack(fill='x'); self.panel_list.bind('<<ListboxSelect>>', self.panel_selected)
        row = ttk.Frame(right); row.pack(fill='x', pady=5)
        ttk.Button(row, text='↑', command=lambda:self.reorder(-1)).pack(side='left', expand=True, fill='x')
        ttk.Button(row, text='↓', command=lambda:self.reorder(1)).pack(side='left', expand=True, fill='x')
        ttk.Button(right, text='Sắp thứ tự tự động', command=self.sort).pack(fill='x', pady=4)
        ttk.Label(right, text='Ảnh sau khi cắt').pack(anchor='w', pady=(15, 5))
        self.preview = tk.Label(right, bg=BG, height=15); self.preview.pack(fill='x')
        self.details = tk.StringVar(value='Chọn ảnh để bắt đầu.'); ttk.Label(right, textvariable=self.details, wraplength=225).pack(fill='x', pady=10)
        ttk.Label(right, text='JPG nền trắng: đưa vào Flow\nPNG alpha: giữ đúng khung chéo\nẢnh gốc được giữ nguyên.', wraplength=225).pack(side='bottom', fill='x', pady=10)
        self.status = tk.StringVar(value='Chọn ảnh hoặc thư mục. Tool sẽ tự nhận panel, sau đó xem đường cắt trước khi xuất.')
        tk.Label(self, textvariable=self.status, anchor='w', bg=BG, fg=ACCENT, padx=12, pady=8).pack(fill='x', side='bottom')
        self.after(120, self.poll)
        if len(sys.argv) > 1:
            self.after(200, lambda: self.import_paths([Path(p) for p in sys.argv[1:]]))

    @property
    def entry(self):
        return self.entries[self.index] if 0 <= self.index < len(self.entries) else None

    def checkpoint(self):
        if self.entry:
            self.history.append((self.index, copy.deepcopy(self.entry['panels'])))
            self.history = self.history[-60:]

    def choose(self):
        paths = filedialog.askopenfilenames(title='Chọn trang manga', filetypes=[('Ảnh', '*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff')])
        if paths: self.import_paths([Path(p) for p in paths])

    def folder(self):
        path = filedialog.askdirectory(title='Thư mục chứa ảnh manga')
        if path: self.import_paths(sorted([p for p in Path(path).iterdir() if p.suffix.lower() in ('.jpg','.jpeg','.png','.webp','.bmp','.tif','.tiff')], key=natural_key))

    def import_paths(self, paths):
        if self.busy: return
        if not paths: return
        self.busy = True; self.status.set('Đang đọc và tự cắt ảnh…')
        sensitivity = self.sensitivity.get()
        existing = {str(e['path'].resolve()) for e in self.entries}
        def work():
            try:
                for path in paths:
                    if str(path.resolve()) in existing: continue
                    image = read_image(path)
                    panels = detect_panels(image, sensitivity)
                    self.jobs.put(('add', {'path':path.resolve(), 'image':image, 'panels':panels}))
                self.jobs.put(('done', 'Đã tự cắt. Viền vàng cần kiểm tra; chọn panel để xem ảnh xuất.'))
            except Exception as error: self.jobs.put(('error', str(error)))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, data = self.jobs.get_nowait()
                if kind == 'add':
                    self.entries.append(data); self.pages.insert('end', f"{data['path'].name}  ({len(data['panels'])})")
                    if self.index < 0: self.show_page(0)
                    self.status.set(f"Đã cắt {data['path'].name}: {len(data['panels'])} panel")
                elif kind == 'replace':
                    i, panels = data; self.entries[i]['panels'] = panels
                    if i == self.index: self.refresh()
                elif kind == 'done':
                    self.busy = False; self.status.set(data); self.refresh_page_names()
                elif kind == 'error':
                    self.busy = False; self.status.set('Có lỗi.'); messagebox.showerror('Không hoàn tất', data)
        except queue.Empty: pass
        self.after(120, self.poll)

    def refresh_page_names(self):
        self.pages.delete(0, 'end')
        for e in self.entries: self.pages.insert('end', f"{e['path'].name}  ({len(e['panels'])})")
        if self.index >= 0: self.pages.selection_set(self.index)

    def page_selected(self, event):
        sel = self.pages.curselection()
        if sel: self.show_page(sel[0])

    def show_page(self, index):
        self.index = index; self.selected = []; self.pending = []; self.zoom = 1; self.refresh()

    def refresh(self):
        self.panel_list.delete(0, 'end')
        if not self.entry: return
        for i,p in enumerate(self.entry['panels']):
            warning = '  ⚠ kiểm tra' if p.confidence < .7 else ''
            self.panel_list.insert('end', f'Panel {i+1:02d}{warning}')
        for i in self.selected:
            if i < len(self.entry['panels']): self.panel_list.selection_set(i)
        self.draw(); self.update_preview()

    def panel_selected(self, event):
        self.selected = list(self.panel_list.curselection()); self.draw(); self.update_preview()

    def draw(self):
        self.canvas.delete('all')
        if not self.entry: return
        image = self.entry['image']; cw,ch = self.canvas.winfo_width(),self.canvas.winfo_height()
        self.scale = min((cw-20)/image.width,(ch-20)/image.height)*self.zoom
        iw,ih = max(1,round(image.width*self.scale)),max(1,round(image.height*self.scale))
        self.offset = ((cw-iw)/2,(ch-ih)/2)
        self.photo = ImageTk.PhotoImage(image.resize((iw,ih),Image.Resampling.LANCZOS))
        self.canvas.create_image(*self.offset, image=self.photo, anchor='nw')
        for i,p in enumerate(self.entry['panels']):
            points = [self.to_screen(xy) for xy in p.points]
            color = ACCENT if i in self.selected else ('#ffc15a' if p.confidence<.7 else '#ff5e7e')
            flat = [v for xy in points for v in xy]
            self.canvas.create_polygon(*flat, outline=color, fill='', width=3 if i in self.selected else 2)
            x,y = points[0]; self.canvas.create_oval(x-13,y-13,x+13,y+13,fill=BG,outline=color)
            self.canvas.create_text(x,y,text=str(i+1),fill=FG,font=('Segoe UI',10,'bold'))
            if i in self.selected:
                for x,y in points: self.canvas.create_rectangle(x-5,y-5,x+5,y+5,fill=color,outline=BG)
        if self.pending:
            points=[self.to_screen(p) for p in self.pending]
            for x,y in points: self.canvas.create_oval(x-4,y-4,x+4,y+4,fill=ACCENT)
            if len(points)>1: self.canvas.create_line(*[v for p in points for v in p],fill=ACCENT,width=2)

    def to_screen(self,p): return (p[0]*self.scale+self.offset[0],p[1]*self.scale+self.offset[1])
    def to_image(self,x,y):
        im=self.entry['image']
        return [min(im.width-1,max(0,(x-self.offset[0])/self.scale)),min(im.height-1,max(0,(y-self.offset[1])/self.scale))]

    def click(self,event):
        if not self.entry or self.busy:return
        xy=self.to_image(event.x,event.y)
        if self.mode=='add': self.pending.append(xy);self.draw();return
        if self.mode=='split':
            if len(self.selected)!=1:self.status.set('Chọn một panel trước khi chia.');return
            self.pending.append(xy)
            if len(self.pending)==2:
                i=self.selected[0];pieces=split_polygon(self.entry['panels'][i].points,*self.pending)
                if len(pieces)==2:
                    self.checkpoint();self.entry['panels'][i:i+1]=[Panel(p,1,'Đã chia thủ công') for p in pieces]
                    self.entry['panels']=reading_order(self.entry['panels']);self.selected=[]
                else:self.status.set('Đường chia phải đi qua bên trong panel.')
                self.pending=[];self.mode='select';self.refresh()
            else:self.draw()
            return
        for i in self.selected:
            for j,p in enumerate(self.entry['panels'][i].points):
                px,py=self.to_screen(p)
                if (px-event.x)**2+(py-event.y)**2<100:
                    self.checkpoint();self.dragging=(i,j);return
        hits=[i for i,p in enumerate(self.entry['panels']) if cv2.pointPolygonTest(np.asarray(p.points,np.float32),tuple(xy),False)>=0]
        self.selected=hits[-1:] if hits else [];self.refresh()

    def motion(self,event):
        if self.dragging:
            i,j=self.dragging;self.entry['panels'][i].points[j]=self.to_image(event.x,event.y)
            self.entry['panels'][i].confidence=1;self.entry['panels'][i].note='Đã chỉnh góc thủ công';self.draw()

    def release(self,event):
        if self.dragging:self.dragging=None;self.update_preview()

    def update_preview(self):
        if not self.entry or len(self.selected)!=1:
            self.preview.configure(image='',text='Chọn một panel',fg=FG);self.details.set('Ctrl / Shift trong danh sách để chọn nhiều panel khi gộp.');return
        p=self.entry['panels'][self.selected[0]]
        crop,_,_=make_crop(self.entry['image'],p);size=crop.size;crop.thumbnail((230,290))
        self.preview_photo=ImageTk.PhotoImage(crop);self.preview.configure(image=self.preview_photo,text='',height=0)
        self.details.set(f'Panel {self.selected[0]+1}: {size[0]} × {size[1]} px\n{p.note or "Kéo các điểm góc nếu cần tinh chỉnh."}')

    def set_mode(self,mode):
        self.mode=mode;self.pending=[]
        self.status.set({'select':'Bấm chọn panel; kéo điểm góc để sửa đường cắt.','add':'Bấm lần lượt các góc; Enter hoặc bấm đúp để đóng đa giác.','split':'Chọn một panel, bấm hai điểm tạo đường chia (có thể bấm ngoài panel).'}[mode])

    def finish_polygon(self,event=None):
        if self.mode!='add' or len(self.pending)<3:return
        self.checkpoint();hull=cv2.convexHull(np.asarray(self.pending,np.float32)).reshape(-1,2)
        self.entry['panels'].append(Panel(hull.tolist(),1,'Đã vẽ thủ công'));self.selected=[len(self.entry['panels'])-1]
        self.pending=[];self.mode='select';self.refresh()

    def cancel(self):self.pending=[];self.mode='select';self.draw()
    def fit(self):self.zoom=1;self.draw()
    def wheel(self,event):self.zoom=min(3,max(.65,self.zoom*(1.12 if event.delta>0 else 1/1.12)));self.draw()

    def delete(self):
        if not self.entry or not self.selected:return
        self.checkpoint()
        for i in sorted(self.selected,reverse=True):del self.entry['panels'][i]
        self.selected=[];self.refresh()

    def merge(self):
        if not self.entry or len(self.selected)<2:self.status.set('Chọn ít nhất hai panel trong danh sách để gộp.');return
        self.checkpoint();points=[p for i in self.selected for p in self.entry['panels'][i].points]
        hull=cv2.convexHull(np.asarray(points,np.float32)).reshape(-1,2).tolist()
        at=min(self.selected)
        for i in sorted(self.selected,reverse=True):del self.entry['panels'][i]
        self.entry['panels'].insert(at,Panel(hull,1,'Đã gộp thủ công'));self.selected=[at];self.refresh()

    def undo(self):
        if not self.history:return
        index,panels=self.history.pop();self.entries[index]['panels']=panels;self.index=index;self.selected=[];self.refresh();self.refresh_page_names()

    def reorder(self,direction):
        if not self.entry or len(self.selected)!=1:return
        i=self.selected[0];j=i+direction
        if 0<=j<len(self.entry['panels']):
            self.checkpoint();ps=self.entry['panels'];ps[i],ps[j]=ps[j],ps[i];self.selected=[j];self.refresh()

    def sort(self):
        if not self.entry:return
        self.checkpoint();self.entry['panels']=reading_order(self.entry['panels']);self.selected=[];self.refresh()

    def auto_current(self):self.detect([self.index] if self.entry else [])
    def auto_all(self):self.detect(list(range(len(self.entries))))
    def detect(self,indices):
        if self.busy or not indices:return
        if any(self.entries[i]['panels'] for i in indices) and not messagebox.askyesno('Tự nhận lại','Tự nhận lại sẽ thay đường cắt hiện tại. Có thể Hoàn tác trang đang chọn. Tiếp tục?'):return
        self.checkpoint();self.busy=True;self.status.set('Đang nhận panel…');sensitivity=self.sensitivity.get()
        def work():
            try:
                for i in indices:self.jobs.put(('replace',(i,detect_panels(self.entries[i]['image'],sensitivity))))
                self.jobs.put(('done','Đã tự nhận lại panel. Kiểm tra đường cắt trước khi xuất.'))
            except Exception as e:self.jobs.put(('error',str(e)))
        threading.Thread(target=work,daemon=True).start()

    def export_current(self):self.export([self.entry] if self.entry else [])
    def export_all(self):self.export(self.entries)
    def export(self,entries):
        if self.busy or not entries:return
        path=filedialog.askdirectory(title='Chọn thư mục xuất panel')
        if not path:return
        self.busy=True;self.status.set('Đang xuất JPG, PNG và đường cắt…')
        snapshots=[{'path':e['path'],'image':e['image'],'panels':copy.deepcopy(e['panels'])} for e in entries]
        def work():
            try:
                total=0
                for e in snapshots:export_page(e['image'],e['panels'],e['path'],path);total+=len(e['panels'])
                save_session(snapshots,Path(path)/'phien_cat.json')
                self.jobs.put(('done',f'Đã xuất {total} panel vào {path}. JPG dùng cho Flow; PNG giữ nền trong suốt.'))
            except Exception as e:self.jobs.put(('error',str(e)))
        threading.Thread(target=work,daemon=True).start()

    def save(self):
        if not self.entries:return
        path=filedialog.asksaveasfilename(title='Lưu đường cắt để sửa tiếp',defaultextension='.json',filetypes=[('Phiên cắt','*.json')])
        if path:save_session(self.entries,path);self.status.set('Đã lưu phiên cắt.')

    def open_session(self):
        if self.busy:return
        path=filedialog.askopenfilename(title='Mở phiên cắt',filetypes=[('Phiên cắt','*.json')])
        if not path:return
        try:self.entries=load_session(path);self.history=[];self.index=0 if self.entries else -1;self.selected=[];self.refresh_page_names();self.refresh()
        except Exception as e:messagebox.showerror('Không mở được phiên',str(e))

    def help(self):
        messagebox.showinfo('Cách dùng','1. Chọn ảnh hoặc chọn cả thư mục. Tool tự cắt.\n2. Xem viền đỏ trên ảnh. Viền vàng cần kiểm tra.\n3. Chọn panel và kéo các điểm góc nếu cần.\n4. Nếu dính khung: Chia panel rồi bấm hai điểm của đường cắt.\n5. Nếu bị tách thừa: Ctrl chọn nhiều mục rồi Gộp.\n6. Xuất tất cả: mỗi trang có JPG nền trắng cho Flow, PNG alpha, đường cắt và JSON.\n\nKhung chéo được giữ bằng mặt nạ đa giác, không dùng hộp chữ nhật để lấy cả khung hàng xóm. Bong bóng thoại trong panel được giữ nguyên.\n\nVới trang không viền hoặc chữ chồng qua nhiều panel, cần kiểm tra và sửa. Không có thuật toán hình học bảo đảm 100% trên mọi manga.')


if __name__=='__main__':
    App().mainloop()
