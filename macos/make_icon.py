# -*- coding: utf-8 -*-
"""Draws LocalASR's app icon (white microphone on a blue rounded square) and writes
it as an .icns file:  python macos/make_icon.py OUT.icns"""
import os
import subprocess
import sys
import tempfile

from AppKit import (
    NSBezierPath,
    NSBitmapImageFileTypePNG,
    NSBitmapImageRep,
    NSColor,
    NSCompositingOperationDestinationIn,
    NSGradient,
    NSGraphicsContext,
    NSImage,
    NSImageSymbolConfiguration,
    NSMakeRect,
)


def draw_png(px: int, path: str):
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, px, px, 8, 4, True, False, "NSDeviceRGBColorSpace", 0, 0)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))

    # macOS icon grid: the shape is ~80% of the canvas, corner radius ~22% of the shape
    inset = px * 0.1
    side = px - 2 * inset
    shape = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        NSMakeRect(inset, inset, side, side), side * 0.225, side * 0.225)
    NSGradient.alloc().initWithStartingColor_endingColor_(
        NSColor.colorWithSRGBRed_green_blue_alpha_(0.20, 0.55, 1.0, 1.0),
        NSColor.colorWithSRGBRed_green_blue_alpha_(0.05, 0.28, 0.80, 1.0),
    ).drawInBezierPath_angle_(shape, -90)

    cfg = NSImageSymbolConfiguration.configurationWithPointSize_weight_(side * 0.48, 0.3)
    mic = NSImage.imageWithSystemSymbolName_accessibilityDescription_("mic.fill", None) \
        .imageWithSymbolConfiguration_(cfg)
    w, h = mic.size().width, mic.size().height
    tinted = NSImage.alloc().initWithSize_(mic.size())
    tinted.lockFocus()
    NSColor.whiteColor().set()
    NSBezierPath.fillRect_(NSMakeRect(0, 0, w, h))
    mic.drawInRect_fromRect_operation_fraction_(NSMakeRect(0, 0, w, h), NSMakeRect(0, 0, 0, 0), NSCompositingOperationDestinationIn, 1.0)
    tinted.unlockFocus()
    tinted.drawInRect_(NSMakeRect((px - w) / 2, (px - h) / 2, w, h))

    NSGraphicsContext.restoreGraphicsState()
    rep.representationUsingType_properties_(NSBitmapImageFileTypePNG, None).writeToFile_atomically_(path, True)


def main(out: str):
    with tempfile.TemporaryDirectory() as tmp:
        iconset = os.path.join(tmp, "AppIcon.iconset")
        os.mkdir(iconset)
        for size in (16, 32, 128, 256, 512):
            draw_png(size, f"{iconset}/icon_{size}x{size}.png")
            draw_png(size * 2, f"{iconset}/icon_{size}x{size}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", out], check=True)


if __name__ == "__main__":
    main(sys.argv[1])
