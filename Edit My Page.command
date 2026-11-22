#!/bin/bash
QUIET_SELF="$0"; . "$HOME/Projects/_tools/launch/quiet.sh" 2>/dev/null   # no Terminal window left behind
# Double-click this to open the Shorty D page editor.
cd "$(dirname "$0")"
python3 editor_server.py
