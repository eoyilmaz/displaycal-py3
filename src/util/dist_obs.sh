#!/bin/sh

# Make sure __version__.py is current
./setup.py

appname=`python2 -c "from DisplayCAL import meta;print meta.name"`
version=`python2 -c "from DisplayCAL import meta;print meta.version"`

# OpenSUSE build service
obs_home_repo=home:fhoech/$appname
obs_m_cm_repo=multimedia:color_management/$appname
for obs_repo in "$obs_home_repo" "$obs_m_cm_repo"; do 
  pushd "../obs/$obs_repo"
  osc update
  osc service localrun || (
    wget -O DisplayCAL-$version.tar.gz http://displaycal.net/download/DisplayCAL-$version.tar.gz
    for filename in "appimage.yml" "DisplayCAL.dsc" "DisplayCAL.spec" "debian.changelog" "DisplayCAL.changes" "PKGBUILD" ; do
      wget -O $filename http://displaycal.net/dist/$filename
    done
  )
  # Remove previous version
  for filename in *.tar.gz ; do
    echo "$filename" | grep "^$appname-" > /dev/null && (
      echo "$filename" | grep "^$appname-$version" > /dev/null || (
        osc remove $filename
      )
    )
  done
  # Remove *.tar.gz.1 file (OSC bug when there is a debian target)
  for filename in *.tar.gz.1 ; do
    osc remove --force $filename
  done
  if [ "$obs_repo" == "$obs_m_cm_repo" ] && [ ! -e "$appname-$version.tar.gz" ]; then
    cp "../../$obs_home_repo/$appname-$version.tar.gz" .
  fi
  osc addremove
  osc ci -m "Update to version $version" --noservice
  popd
done
