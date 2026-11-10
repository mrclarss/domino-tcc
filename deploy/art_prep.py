# uso: python3 art_prep.py frasco.jpg redondo.jpg yinyang.jpg -> repo/liga/static/img/
# Remove só o branco de fundo ligado às bordas (flood fill), preservando brancos internos.
import sys; from PIL import Image, ImageDraw, ImageFilter
out="/workspace/liga/repo/liga/static/img/"
def clear(src,dst,size,thr=40):
    im=Image.open(src).convert("RGB"); w,h=im.size
    mark=im.copy()
    for p in [(0,0),(w-1,0),(0,h-1),(w-1,h-1)]:
        ImageDraw.floodfill(mark,p,(255,0,255),thresh=thr)
    mask=Image.new("L",im.size,255); mp=mark.load(); mk=mask.load()
    for y in range(h):
        for x in range(w):
            if mp[x,y]==(255,0,255): mk[x,y]=0
    mask=mask.filter(ImageFilter.GaussianBlur(1.2))
    rgba=im.convert("RGBA"); rgba.putalpha(mask)
    rgba=rgba.crop(mask.getbbox()); rgba.thumbnail((size,size),Image.LANCZOS); rgba.save(out+dst,optimize=True)
f,r,y=sys.argv[1:4]
clear(f,"mascote-frasco.png",512); clear(r,"logo-redondo.png",256); clear(y,"mascote-yinyang.png",512)
