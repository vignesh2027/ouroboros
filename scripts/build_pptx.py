"""Build a .pptx from rendered slide images using only the standard library.

A pptx is an OPC package, which is a zip of XML parts. Each slide here holds a
single full bleed picture, which keeps the XML surface small and robust.

Usage:
    python3 scripts/build_pptx.py <slides_dir> <n_slides> <output.pptx>
"""

import os
import sys
import zipfile

SLIDES = sys.argv[1] if len(sys.argv) > 1 else "slides_png"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 8
OUT = sys.argv[3] if len(sys.argv) > 3 else "deck.pptx"

W, H = 12192000, 6858000          # 13.333in by 7.5in in EMU, 16:9

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
HDR = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
RELS = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'


def content_types():
    slides = "".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType='
        f'"application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, N + 1))
    return HDR + (
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
        f'{slides}</Types>')


def empty_tree():
    return ('<p:cSld><p:spTree>'
            '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
            '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            '</p:spTree></p:cSld>')


CLRMAP = ('bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" '
          'accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" '
          'hlink="hlink" folHlink="folHlink"')


def theme():
    pairs = [("dk2", "111111"), ("lt2", "EEEEEE"), ("accent1", "1B5E9E"),
             ("accent2", "C0392B"), ("accent3", "157A57"), ("accent4", "9A7B10"),
             ("accent5", "6B6B6B"), ("accent6", "D5D5D5"), ("hlink", "1B5E9E"),
             ("folHlink", "6B6B6B")]
    clr = ('<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>'
           '<a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>'
           + "".join(f'<a:{n}><a:srgbClr val="{v}"/></a:{n}>' for n, v in pairs))
    solid = '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    ln = ('<a:lnStyleLst>'
          + "".join(f'<a:ln w="{w}">{solid}</a:ln>' for w in (6350, 12700, 19050))
          + '</a:lnStyleLst>')
    eff = ('<a:effectStyleLst>'
           + '<a:effectStyle><a:effectLst/></a:effectStyle>' * 3
           + '</a:effectStyleLst>')
    font = ('<a:majorFont><a:latin typeface="Helvetica Neue"/><a:ea typeface=""/>'
            '<a:cs typeface=""/></a:majorFont>'
            '<a:minorFont><a:latin typeface="Helvetica Neue"/><a:ea typeface=""/>'
            '<a:cs typeface=""/></a:minorFont>')
    return HDR + (
        f'<a:theme xmlns:a="{A}" name="Ouroboros"><a:themeElements>'
        f'<a:clrScheme name="Ouroboros">{clr}</a:clrScheme>'
        f'<a:fontScheme name="Ouroboros">{font}</a:fontScheme>'
        f'<a:fmtScheme name="Ouroboros">'
        f'<a:fillStyleLst>{solid * 3}</a:fillStyleLst>{ln}{eff}'
        f'<a:bgFillStyleLst>{solid * 3}</a:bgFillStyleLst>'
        f'</a:fmtScheme></a:themeElements>'
        f'<a:objectDefaults/><a:extraClrSchemeLst/></a:theme>')


def slide(i):
    return HDR + (
        f'<p:sld xmlns:a="{A}" xmlns:r="{R}" xmlns:p="{P}"><p:cSld><p:spTree>'
        f'<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        f'<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        f'<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        f'<p:pic><p:nvPicPr>'
        f'<p:cNvPr id="2" name="Slide {i}" descr="Ouroboros Phase 1 review, slide {i}"/>'
        f'<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
        f'<p:blipFill><a:blip r:embed="rId1"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
        f'<p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{W}" cy="{H}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
        f'</p:spTree></p:cSld>'
        f'<p:clrMapOvr><a:overrideClrMapping {CLRMAP}/></p:clrMapOvr></p:sld>')


def main():
    ids = "".join(f'<p:sldId id="{255 + i}" r:id="rId{i + 1}"/>' for i in range(1, N + 1))
    pres_rels = [f'<Relationship Id="rId1" Type="{R}/slideMaster" Target="slideMasters/slideMaster1.xml"/>']
    pres_rels += [f'<Relationship Id="rId{i + 1}" Type="{R}/slide" Target="slides/slide{i}.xml"/>'
                  for i in range(1, N + 1)]
    pres_rels.append(f'<Relationship Id="rId{N + 2}" Type="{R}/theme" Target="theme/theme1.xml"/>')

    parts = {
        "[Content_Types].xml": content_types(),
        "_rels/.rels": HDR + RELS + f'<Relationship Id="rId1" Type="{R}/officeDocument" Target="ppt/presentation.xml"/></Relationships>',
        "ppt/presentation.xml": HDR + (
            f'<p:presentation xmlns:a="{A}" xmlns:r="{R}" xmlns:p="{P}">'
            f'<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
            f'<p:sldIdLst>{ids}</p:sldIdLst>'
            f'<p:sldSz cx="{W}" cy="{H}"/><p:notesSz cx="{H}" cy="{W}"/></p:presentation>'),
        "ppt/_rels/presentation.xml.rels": HDR + RELS + "".join(pres_rels) + "</Relationships>",
        "ppt/slideMasters/slideMaster1.xml": HDR + (
            f'<p:sldMaster xmlns:a="{A}" xmlns:r="{R}" xmlns:p="{P}">{empty_tree()}'
            f'<p:clrMap {CLRMAP}/>'
            f'<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
            f'</p:sldMaster>'),
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": HDR + RELS + (
            f'<Relationship Id="rId1" Type="{R}/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
            f'<Relationship Id="rId2" Type="{R}/theme" Target="../theme/theme1.xml"/></Relationships>'),
        "ppt/slideLayouts/slideLayout1.xml": HDR + (
            f'<p:sldLayout xmlns:a="{A}" xmlns:r="{R}" xmlns:p="{P}" type="blank" preserve="1">'
            f'{empty_tree()}</p:sldLayout>'),
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": HDR + RELS + (
            f'<Relationship Id="rId1" Type="{R}/slideMaster" Target="../slideMasters/slideMaster1.xml"/>'
            f'</Relationships>'),
        "ppt/theme/theme1.xml": theme(),
    }
    for i in range(1, N + 1):
        parts[f"ppt/slides/slide{i}.xml"] = slide(i)
        parts[f"ppt/slides/_rels/slide{i}.xml.rels"] = HDR + RELS + (
            f'<Relationship Id="rId1" Type="{R}/image" Target="../media/image{i}.png"/>'
            f'<Relationship Id="rId2" Type="{R}/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
            f'</Relationships>')

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)
        for i in range(1, N + 1):
            z.write(os.path.join(SLIDES, f"s{i}.png"), f"ppt/media/image{i}.png")

    print(f"wrote {OUT}  ({os.path.getsize(OUT)/1024/1024:.2f} MB, {N} slides, 1920x1080)")


if __name__ == "__main__":
    main()
