#!/bin/sh

function createpreset() {
  local root="`dirname \"$0\"`/.."
  echo "$1"
  colprof  -ql -aG -C "Created with DisplayCAL and ArgyllCMS" -D "DisplayCAL calibration preset: $1" "$root/misc/ti3/$2"
  mv -i "$root/misc/ti3/$2".ic? "$root/DisplayCAL/presets/$2.icc" && python2 "$root/util/update_presets.py" "$2"
  echo ""
}

createpreset "Default"      "default"
createpreset "eeColor"      "video_eeColor"
createpreset "Laptop"       "laptop"
createpreset "madVR"        "video_madVR"
createpreset "madVR ST.2084" "video_madVR_ST2084"
createpreset "Office & Web" "office_web"
createpreset "Photo"        "photo"
createpreset "Prisma"       "video_Prisma"
createpreset "ReShade"      "video_ReShade"
createpreset "Resolve"      "video_resolve"
createpreset "Resolve ST.2084" "video_resolve_ST2084_clip"
createpreset "Softproof"    "softproof"
createpreset "sRGB"         "sRGB"
createpreset "Video"        "video"
