#!/usr/bin/env bash
set -euo pipefail

for profile in /profiles/*.yml /profiles/*.yaml; do
    [[ -f "${profile}" ]] || continue
    stem=$(basename "${profile}")
    stem="${stem%.yml}"
    stem="${stem%.yaml}"
    mkdir -p "/archives/${stem}"
    echo "INFO: generating archive for ${profile} → /archives/${stem}/${stem}"
    if ! pmlogsynth -o "/archives/${stem}/${stem}" "${profile}"; then
        echo "ERROR: pmlogsynth failed for ${profile}"
        exit 1
    fi
    echo "INFO: archive ${stem} complete"
done

echo "INFO: all profiles generated successfully"
