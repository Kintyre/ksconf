#!/bin/bash
# shellcheck disable=SC1091
#
# Build the Splunk APP

PY=python2.7
# https://stackoverflow.com/a/246128/315892
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PROJECT_DIR=$(dirname "$DIR")
APP=${DIR}/ksconf
PIP_TARGET=${APP}/bin/lib
DOCS=${PROJECT_DIR}/docs
APP_DOCS=$APP/appserver/static/docs

echo "SCRIPT DIR:  $DIR"
cd "$DIR" || { echo "Can't find $DIR"; exit 1; }

if [[ -d $PIP_TARGET ]]; then echo "Clean old $PIP_TARGET"; rm -rf "$PIP_TARGET"; fi
mkdir -p "$PIP_TARGET"

$PY -m pip install --target="$PIP_TARGET" "${PROJECT_DIR}"

# Remove all the 'bin/bin/ksconf' and other files, since none of them will be usable on the target system
rm -rf "${PIP_TARGET:?}/bin"

# Splunk packaging standards bans all compiled python files
find "$PIP_TARGET" -type f -name '*.py[co]' -delete

# I'd like to remove the dist-info folders too, but not sure that's a good idea since we'd like to have entrypoints work.  Just not sure how that will work with app installs where things are never cleaned up.  May need to implement my own manifest and cleanup mechanism....?!?!
( cd "$PIP_TARGET" || exit 9 ; find . -ls > "$PIP_TARGET/../manifest.txt"; )


# Wonky workaround, run setup.py first so that ksconf/_version.py is created.  :-(
$PY setup.py --help >/dev/null 2>&1

# Load KSCONF_VERSION and KSCONF_BUILD; This assumes setup.py was run, causing _version.py to be generated
eval "$(cd "$PROJECT_DIR" || exit 8; $PY -m ksconf._version)"
export KSCONF_VERSION KSCONF_BUILD

echo "KSCONF v$KSCONF_VERSION"

(
    cd "${DOCS}" || { echo "Can't find docs."; exit 1; }
    if [[ ! -d venv ]];
    then
        echo "First time setup: Creating 'venv' with all requirements for dev"
        $PY -m pip virtualenv
        $PY -m virtualenv venv
        . venv/bin/activate
        python -m pip install -r $DIR/requirements.txt
  else
        . venv/bin/activate
  fi
  # Use the classic theme (~ 1Mb output vs 11+ mb, due to web fonts)
  export KSCONF_DOCS_THEME="classic"
  echo "Making HTML docs"
  make html || { echo "Failed to make docs."; exit 2; }
  rm -rf "$APP_DOCS"
  mkdir "$(dirname $APP_DOCS)"
  echo "Copying docs into the KSCONF Splunk app"
  cp -a "$DOCS/build/html" "$APP_DOCS"
)
sed -E "s/\\{\\{BUILD\\}\\}/${KSCONF_BUILD}/; s/\\{\\{VERSION\\}\\}/${KSCONF_VERSION}/" "$APP/default/app.conf.template" > "$APP/default/app.conf"


# MAC OSX undocumented hack to prevent creation of '._*' folders
export COPYFILE_DISABLE=1
DIST="$PROJECT_DIR/zdist"

test -d "$DIST" || mkdir "$DIST"
echo "Building Splunk app tarball"
APP_FILE=$DIST/splunk-$KSCONF_VERSION.tgz
tar -czvf "$APP_FILE" "ksconf"
echo "Wrote Splunk app to $APP_FILE"
