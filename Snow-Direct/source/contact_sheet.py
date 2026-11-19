"""Make a shot index from actual rendered images using Pillow."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from render import frame_cache
ROOT=Path(__file__).resolve().parent.parent
frames=[(65,"01   RECEPTION"),(177,"02   MY VOICE"),(261,"03   THREE KNOCKS"),
        (403,"04   SOMEONE OUTSIDE"),(509,"05   ONE INCH"),(561,"05   OPEN"),
        (645,"06   EMPTY THRESHOLD"),(777,"07   TRANSMIT")]
def main():
    sheet=Image.new('RGB',(992,4*303),(22,30,33));d=ImageDraw.Draw(sheet)
    font=ImageFont.load_default(size=15)
    for n,(frame,name) in enumerate(frames):
        candidates=[frame_cache(s)/f'snow-{frame:04}.png' for s in (1,2)]+[ROOT/'work/preview'/f'{frame:04}.png']
        p=next(p for p in candidates if p.is_file())
        x=12+(n%2)*490;y=10+(n//2)*303
        with Image.open(p) as im:sheet.paste(im.convert('RGB').resize((477,268),Image.Resampling.LANCZOS),(x,y))
        d.text((x+1,y+274),name,font=font,fill=(238,225,199))
        d.text((x+406,y+274),f'f. {frame:03}',font=font,fill=(162,183,180))
    sheet.save(ROOT/'Shots.jpg',quality=92,subsampling=0)
if __name__=='__main__':main()
