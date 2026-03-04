#!/usr/bin/env bash
set -euo pipefail

# Start archives 70 minutes ago so data falls within a -90min query window
# regardless of when the generator runs (avoids midnight-default staleness).
START_TIME=$(date -u -d '-70 minutes' '+%Y-%m-%d %H:%M:%S UTC' 2>/dev/null \
          || date -u -v-70M '+%Y-%m-%d %H:%M:%S UTC')

for profile in /profiles/*.yml; do
    stem=$(basename "${profile}" .yml)
    mkdir -p "/archives/${stem}"
    echo "INFO: generating archive for ${profile} → /archives/${stem}/${stem} (start: ${START_TIME})"
    if ! pmlogsynth --start "${START_TIME}" -o "/archives/${stem}/${stem}" "${profile}"; then
        echo "ERROR: pmlogsynth failed for ${profile}"
        exit 1
    fi
    echo "INFO: archive ${stem} complete"
done

echo "INFO: all profiles generated successfully"
